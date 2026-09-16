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

gather_training_examples() and evaluate_logistic_holdout() are shared
with backtest_pipeline.py, so a genuine chronological holdout
evaluation (never in-sample) is the ONE source of truth both the
/features/nfl/logistic/train and /backtest/nfl/run?model=logistic
endpoints report -- there's no second, looser "backtest" number that
disagrees with training's own honest self-assessment.
"""

import math
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.db.models.core import Game, League, TeamGameFeatures, Prediction, IngestionLog, PredictionSnapshot
from app.features.logistic_model import SimpleLogisticRegression

MIN_TRAINING_SAMPLES = 10
EPSILON = 1e-15


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


def gather_training_examples(db: Session, league_id: int) -> List[Tuple[List[float], float]]:
    """
    Every completed, fully-featured game for a league, IN CHRONOLOGICAL
    ORDER -- the shared starting point for both training and honest
    holdout evaluation. Chronological order matters: a random split
    would let the model be evaluated on games earlier than some of its
    own training games, which isn't how this model is actually used
    (always predicting forward from what's already happened).
    """
    all_games = (
        db.query(Game)
        .filter_by(league_id=league_id)
        .order_by(Game.game_date.asc())
        .all()
    )
    features_lookup = {}
    for row in (
        db.query(TeamGameFeatures)
        .join(Game, Game.id == TeamGameFeatures.game_id)
        .filter(Game.league_id == league_id)
        .all()
    ):
        features_lookup[(row.game_id, row.team_id)] = row

    examples: List[Tuple[List[float], float]] = []
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
        examples.append((vec, outcome))

    return examples


def evaluate_logistic_holdout(db: Session, league_slug: str) -> dict:
    """
    Trains on the chronologically earlier ~80% of completed games and
    evaluates accuracy/brier/log_loss on the later ~20% the model never
    saw -- a genuine out-of-sample measurement, not the model grading
    its own memorized homework.
    """
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    examples = gather_training_examples(db, league.id)
    if len(examples) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            f"Only {len(examples)} usable completed games with full features on file -- "
            f"need at least {MIN_TRAINING_SAMPLES} to evaluate a logistic regression model "
            f"honestly. Run more game syncs and the feature/elo compute endpoints first."
        )

    split_idx = int(len(examples) * 0.8)
    train_examples = examples[:split_idx]
    holdout_examples = examples[split_idx:]

    if len(train_examples) < MIN_TRAINING_SAMPLES or len(holdout_examples) < 5:
        raise ValueError(
            f"Not enough games on file for a meaningful holdout split "
            f"({len(train_examples)} train / {len(holdout_examples)} holdout). "
            f"Run more game syncs first."
        )

    model = SimpleLogisticRegression()
    model.fit(
        [vec for vec, _ in train_examples],
        [outcome for _, outcome in train_examples],
    )
    preds = model.predict_proba([vec for vec, _ in holdout_examples])
    actuals = [outcome for _, outcome in holdout_examples]

    decisive = [(p, a) for p, a in zip(preds, actuals) if a != 0.5]
    correct = sum(1 for p, a in decisive if (p > 0.5) == (a == 1.0))
    accuracy = correct / len(decisive) if decisive else None

    brier_score = sum((p - a) ** 2 for p, a in zip(preds, actuals)) / len(preds)

    total_log_loss = 0.0
    for p, a in zip(preds, actuals):
        p_clamped = min(max(p, EPSILON), 1 - EPSILON)
        total_log_loss += -(a * math.log(p_clamped) + (1 - a) * math.log(1 - p_clamped))
    log_loss = total_log_loss / len(preds)

    return {
        "games_evaluated": len(holdout_examples),
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "brier_score": round(brier_score, 5),
        "log_loss": round(log_loss, 5),
    }


def train_logistic_for_league(db: Session, league_slug: str) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    all_games = (
        db.query(Game)
        .filter_by(league_id=league.id)
        .order_by(Game.game_date.asc())
        .all()
    )
    features_lookup = {}
    for row in (
        db.query(TeamGameFeatures)
        .join(Game, Game.id == TeamGameFeatures.game_id)
        .filter(Game.league_id == league.id)
        .all()
    ):
        features_lookup[(row.game_id, row.team_id)] = row

    examples = gather_training_examples(db, league.id)
    if len(examples) < MIN_TRAINING_SAMPLES:
        raise ValueError(
            f"Only {len(examples)} usable completed games with full features on file -- "
            f"need at least {MIN_TRAINING_SAMPLES} to train a logistic regression model "
            f"honestly. Run more game syncs and the feature/elo compute endpoints first."
        )

    # Genuine out-of-sample accuracy, computed the same way the backtest
    # endpoint computes it -- one honest number, not two disagreeing ones.
    holdout_metrics = None
    try:
        holdout_metrics = evaluate_logistic_holdout(db, league_slug)
    except ValueError:
        pass  # not enough games yet for a meaningful holdout split

    # For the model that actually generates live predictions, train on
    # EVERY completed game on file -- more real data makes a better
    # production model. holdout_metrics above is what tells you how
    # trustworthy that production model's predictions really are.
    model = SimpleLogisticRegression()
    model.fit([vec for vec, _ in examples], [outcome for _, outcome in examples])

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

    _log(db, "logistic_pipeline", f"train_{league_slug}", "success", len(examples))
    db.commit()

    return {
        "training_samples": len(examples),
        "predictions_written": predictions_written,
        "holdout_accuracy": holdout_metrics["accuracy"] if holdout_metrics else None,
        "holdout_games": holdout_metrics["games_evaluated"] if holdout_metrics else 0,
        "learned_weights": {
            "elo_gap": round(model.weights[0], 4),
            "rolling_win_pct_gap": round(model.weights[1], 4),
            "point_diff_gap": round(model.weights[2], 4),
            "rest_days_gap": round(model.weights[3], 4),
            "bias": round(model.bias, 4),
        },
    }
