"""
Injury report ingestion pipeline.

Scoped by team, not date range -- API-Sports' /injuries endpoint
gives you a team's CURRENT report, not history, so this always
represents "as of right now" rather than a specific past date.
Re-running it for a team replaces that team's rows with the latest
report rather than appending duplicates.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Protocol
from sqlalchemy.orm import Session

from app.db.models.core import Team, Player, InjuryReport, IngestionLog


class InjuryConnector(Protocol):
    provider_name: str

    def fetch_injuries(self, team_external_id: str) -> list[Dict[str, Any]]: ...


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _get_or_create_player(db: Session, team: Team, external_id: str,
                           name: str, provider: str) -> Player:
    player = db.query(Player).filter_by(external_id=external_id, provider=provider).first()
    if not player:
        player = Player(
            team_id=team.id,
            external_id=external_id,
            provider=provider,
            full_name=name or f"Unknown ({external_id})",
        )
        db.add(player)
        db.flush()
    return player


def run_injury_ingestion(db: Session, connector: InjuryConnector, team: Team) -> dict:
    """
    Fetches and stores the current injury report for one team.
    Returns e.g. {"reports_stored": 4}.
    """
    source = connector.provider_name

    try:
        raw = connector.fetch_injuries(team.external_id)
        _log(db, source, "fetch_injuries", "success", len(raw))
    except Exception as e:
        _log(db, source, "fetch_injuries", "error", 0, str(e))
        db.commit()
        raise

    # Re-running for this team replaces its existing report rather
    # than stacking up duplicates from every sync.
    db.query(InjuryReport).filter_by(team_id=team.id, source=source).delete()

    stored = 0
    for entry in raw:
        player = _get_or_create_player(
            db, team, entry["player_external_id"], entry["player_name"], source,
        )
        db.add(InjuryReport(
            player_id=player.id,
            team_id=team.id,
            report_date=datetime.now(timezone.utc),
            status=entry["status"],
            description=entry.get("description"),
            source=source,
        ))
        stored += 1

    _log(db, source, "store_injuries", "success", stored)
    db.commit()

    return {"reports_stored": stored}
