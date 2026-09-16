"""
Logistic regression pipeline (Milestone 5, part 2 -- second baseline
model).

Unlike Elo (which updates incrementally, game by game), logistic
regression needs to be trained on a BATCH of completed games at once:
gather every completed game's pre-game features, pair each with its
actual outcome, fit the model, then use the fitted model to predict
every game -- played or not.

Deliberately requires a minimum number of training examples before
it will train at all (MIN_TRAINING_SAMPLES). Fitting a model on a
handful of games and presenting it as a real prediction would be
misleading.

The model itself is NOT persisted between calls -- every call to
train_logistic_for_league() retrains from scratch on whatever
completed games are on file.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.core import Game, League, TeamGameFeatures, Prediction, IngestionLog, PredictionSnapshot
from app.features.logistic_model import SimpleLogisticRegression

MIN_TRAINING_SAMPLES = 10


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _build_feature_vector(home_f: TeamGameFeatures, away_f: TeamGameFeatures) -> Optional[List[float]]:
    if None in (
        home_f.elo_rating, away_f.elo_rating,
        home_f.rolling_win_pct, away_f.rolling_win_pct,
        home_f.rolling_points_for_avg, home_f.rolling_points_against_avg,
        away_f.rolling_points_for_avg, away_f.rolling_points_against_avg,
        home_f.rest_days, away_f.rest_days,
    ):
        return None

    elo_gap = float(home_f.elo_rating) - float(away_f.elo_rating)
    win_pct_gap = float(home_f.rolling_win_pct) - float(away_f.rolling_win_pct)
    home_point_diff = float(home_f.rolling_points_for_avg) - float(home_f.rolling_points_against_avg)
    away_point_diff = float(away_f.rolling_points_for_avg) - float(away_f.rolling_points_against_avg)
    point_diff_gap = home_point_diff - away_point_diff
    rest_gap = float(home_f.rest_days - away_f.rest_days)

    return [elo_gap, win_pct_gap, point_diff_gap, rest_gap]


def _actual_home_win(game: Game) -> Optional[float]:
    if game.status != "final" or game.home_score is None or game.away_score is None:
        return None
    if game.home_score == game.away_score:
        return None
    return 1.0 if game.home_score > game.away_score else 0.0


def train_logistic_for_league(db: Session, league_slug: str) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    all_games = db.query(Game).filter_by(league_id=league.id).all()
    features_lookup = {}
    for row in (
        db.query(TeamGameFeatures)
        .join(Game, Game.id == TeamGameFeatures.game_id)
        .filter(Game.league_id == league.id)
        .all()
    ):
        features_lookup[(row.game_id, row.team_id)] = row

    X_train: List[List[float]] = []
    y_train: List[float] = []
    for game in all_games:
        outcome = _actual_home_win(game)
        if outcome is None:
            continue
        home_f = features_lookup.get((game.id, game.home_team_id))
        away_f = features_lookup.get((game.id, game.away_team_id))
        if not home_f or not away_f:
            continue
        vec = _build_feature_vector(home_f, away_f)
        if vec is None:
            continue
        X_train.append(vec)
        y_train.append(outcome)

    if len(X_train) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            f"Only {len(X_train)} usable completed games with full features on file -- "
            f"need at least {MIN_TRAINING_SAMPLES} to train a logistic regression model "
            f"honestly. Run more game syncs and the feature/elo compute endpoints first."
        )

    model = SimpleLogisticRegression()
    model.fit(X_train, y_train)

    predictions_written = 0
    for game in all_games:
        home_f = features_lookup.get((game.id, game.home_team_id))
        away_f = features_lookup.get((game.id, game.away_team_id))
        if not home_f or not away_f:
            continue
        vec = _build_feature_vector(home_f, away_f)
        if vec is None:
            continue

        home_prob = model.predict_proba([vec])[0]
        away_prob = 1.0 - home_prob

        for team_id, prob in ((game.home_team_id, home_prob), (game.away_team_id, away_prob)):
            existing = (
                db.query(Prediction)
                .filter_by(game_id=game.id, team_id=team_id, model_name="logistic")
                .first()
            )
            if existing:
                existing.win_probability = prob
            else:
                db.add(Prediction(
                    game_id=game.id, team_id=team_id, model_name="logistic", win_probability=prob,
                ))
            db.add(PredictionSnapshot(game_id=game.id, team_id=team_id, model_name="logistic", win_probability=prob))
            predictions_written += 1

    _log(db, "logistic_pipeline", f"train_{league_slug}", "success", len(X_train))
    db.commit()

    return {
        "training_samples": len(X_train),
        "predictions_written": predictions_written,
        "learned_weights": {
            "elo_gap": round(model.weights[0], 4),
            "rolling_win_pct_gap": round(model.weights[1], 4),
            "point_diff_gap": round(model.weights[2], 4),
            "rest_days_gap": round(model.weights[3], 4),
            "bias": round(model.bias, 4),
        },
    }
