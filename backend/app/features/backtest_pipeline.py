"""
Backtesting pipeline (Milestone 6, extended in Milestone 5 part 2 to
support multiple models).

Walks every COMPLETED game in a league, compares a model's pre-game
win probability against what actually happened, and computes three
standard forecast-quality metrics: accuracy, Brier score, and log
loss.

Elo's win probability lives on its own columns in team_game_features
(built first, in Milestone 5 part 1). Every model after it -- starting
with logistic regression -- reads from the generic predictions table
instead. Same aggregation logic either way.
"""

import math
from typing import Optional
from sqlalchemy.orm import Session

from app.db.models.core import Game, League, TeamGameFeatures, Prediction, BacktestRun, IngestionLog

EPSILON = 1e-6
SUPPORTED_MODELS = ("elo", "logistic")


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _actual_home_outcome(game: Game) -> Optional[float]:
    if game.status != "final" or game.home_score is None or game.away_score is None:
        return None
    if game.home_score > game.away_score:
        return 1.0
    elif game.away_score > game.home_score:
        return 0.0
    return 0.5


def _gather_predictions(db: Session, league_id: int, model_name: str) -> list:
    predictions = []

    if model_name == "elo":
        rows = (
            db.query(Game, TeamGameFeatures)
            .join(TeamGameFeatures, (TeamGameFeatures.game_id == Game.id) & (TeamGameFeatures.team_id == Game.home_team_id))
            .filter(Game.league_id == league_id, Game.status == "final")
            .all()
        )
        for game, features in rows:
            actual = _actual_home_outcome(game)
            if features.elo_win_prob is None or actual is None:
                continue
            predictions.append((float(features.elo_win_prob), actual))

    else:
        rows = (
            db.query(Game, Prediction)
            .join(Prediction, (Prediction.game_id == Game.id) & (Prediction.team_id == Game.home_team_id))
            .filter(Game.league_id == league_id, Game.status == "final", Prediction.model_name == model_name)
            .all()
        )
        for game, prediction in rows:
            actual = _actual_home_outcome(game)
            if actual is None:
                continue
            predictions.append((float(prediction.win_probability), actual))

    return predictions


def run_backtest_for_league(db: Session, league_slug: str, model_name: str = "elo") -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"Unknown model_name '{model_name}' -- supported: {', '.join(SUPPORTED_MODELS)}")

    predictions = _gather_predictions(db, league.id, model_name)

    if not predictions:
        raise ValueError(
            f"No completed games with '{model_name}' predictions found for '{league_slug}'. "
            f"Run the feature and {model_name} compute/train endpoints first."
        )

    decisive = [(p, a) for p, a in predictions if a != 0.5]
    correct = sum(1 for p, a in decisive if (p > 0.5) == (a == 1.0))
    accuracy = correct / len(decisive) if decisive else None

    brier_score = sum((p - a) ** 2 for p, a in predictions) / len(predictions)

    total_log_loss = 0.0
    for p, a in predictions:
        p_clamped = min(max(p, EPSILON), 1 - EPSILON)
        total_log_loss += -(a * math.log(p_clamped) + (1 - a) * math.log(1 - p_clamped))
    log_loss = total_log_loss / len(predictions)

    run = BacktestRun(
        league_id=league.id,
        model_name=model_name,
        games_evaluated=len(predictions),
        accuracy=accuracy,
        brier_score=brier_score,
        log_loss=log_loss,
    )
    db.add(run)
    _log(db, "backtest_pipeline", f"backtest_{league_slug}_{model_name}", "success", len(predictions))
    db.commit()

    return {
        "model_name": model_name,
        "games_evaluated": len(predictions),
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "brier_score": round(brier_score, 5),
        "log_loss": round(log_loss, 5),
    }
