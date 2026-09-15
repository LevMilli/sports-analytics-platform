"""
Alerts pipeline (Milestone 9). Generates two kinds of alerts, purely
from data already computed by earlier milestones:

- model_disagreement: Elo and logistic regression give meaningfully
  different win probabilities for the same game.
- low_confidence: the explainability layer's confidence score is
  below a threshold, meaning too little data to trust the prediction.

Only scheduled (not yet played) games are checked. Re-running this
replaces each game's existing alerts of the same type rather than
stacking duplicates.
"""

from sqlalchemy.orm import Session

from app.db.models.core import Game, League, TeamGameFeatures, Prediction, Alert, IngestionLog
from app.features.explain_pipeline import explain_game

DISAGREEMENT_THRESHOLD = 0.15
LOW_CONFIDENCE_THRESHOLD = 30


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _upsert_alert(db: Session, league_id: int, game_id: int, alert_type: str, severity: str, message: str):
    existing = db.query(Alert).filter_by(game_id=game_id, alert_type=alert_type).first()
    if existing:
        existing.severity = severity
        existing.message = message
    else:
        db.add(Alert(
            league_id=league_id, game_id=game_id, alert_type=alert_type,
            severity=severity, message=message,
        ))


def _clear_alert(db: Session, game_id: int, alert_type: str):
    db.query(Alert).filter_by(game_id=game_id, alert_type=alert_type).delete()


def generate_alerts_for_league(db: Session, league_slug: str) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    scheduled_games = (
        db.query(Game)
        .filter(Game.league_id == league.id, Game.status == "scheduled")
        .all()
    )

    alerts_created = 0
    for game in scheduled_games:
        home_f = db.query(TeamGameFeatures).filter_by(game_id=game.id, team_id=game.home_team_id).first()
        logistic_pred = (
            db.query(Prediction)
            .filter_by(game_id=game.id, team_id=game.home_team_id, model_name="logistic")
            .first()
        )

        if home_f and home_f.elo_win_prob is not None and logistic_pred:
            elo_prob = float(home_f.elo_win_prob)
            logistic_prob = float(logistic_pred.win_probability)
            diff = abs(elo_prob - logistic_prob)
            if diff >= DISAGREEMENT_THRESHOLD:
                _upsert_alert(
                    db, league.id, game.id, "model_disagreement", "warning",
                    f"Elo and logistic regression disagree by {diff:.0%} on this game "
                    f"(Elo: {elo_prob:.0%} home win, logistic: {logistic_prob:.0%} home win).",
                )
                alerts_created += 1
            else:
                _clear_alert(db, game.id, "model_disagreement")

        try:
            explanation = explain_game(db, game.id)
            if explanation["confidence"] < LOW_CONFIDENCE_THRESHOLD:
                _upsert_alert(
                    db, league.id, game.id, "low_confidence", "info",
                    f"Only {explanation['confidence']}% confidence -- "
                    f"{explanation['home_team']} and {explanation['away_team']} both have "
                    f"limited recent game history on file ({explanation['sample_size']} sample size).",
                )
                alerts_created += 1
            else:
                _clear_alert(db, game.id, "low_confidence")
        except ValueError:
            continue

    _log(db, "alerts_pipeline", f"generate_{league_slug}", "success", alerts_created)
    db.commit()

    return {"games_checked": len(scheduled_games), "alerts_active": alerts_created}
