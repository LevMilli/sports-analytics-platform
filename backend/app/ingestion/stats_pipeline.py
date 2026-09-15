"""
Box-score stats ingestion pipeline.

Separate from pipeline.py (which handles games) because this operates
on a Game ALREADY in the database rather than fetching a date range --
you need a game's external_id before you can ask a provider for its
box score, so this is naturally a second pass, not part of the same
fetch-a-date-range flow.

Runs: fetch team stats -> fetch player stats -> store both -> log.
Same idempotent-upsert pattern as the games pipeline: re-running for
the same game updates the existing rows rather than duplicating them.
"""

from typing import Any, Dict, Protocol
from sqlalchemy.orm import Session

from app.db.models.core import Game, Team, Player, TeamGameStats, PlayerGameStats, IngestionLog


class StatsConnector(Protocol):
    provider_name: str

    def fetch_team_stats(self, game_external_id: str) -> list[Dict[str, Any]]: ...
    def fetch_player_stats(self, game_external_id: str) -> list[Dict[str, Any]]: ...


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _find_team(db: Session, league_id: int, external_id: str, provider: str):
    return db.query(Team).filter_by(
        league_id=league_id, external_id=external_id, provider=provider
    ).first()


def _get_or_create_player(db: Session, team, external_id: str, name: str, provider: str):
    player = db.query(Player).filter_by(external_id=external_id, provider=provider).first()
    if not player:
        player = Player(
            team_id=team.id if team else None,
            external_id=external_id,
            provider=provider,
            full_name=name or f"Unknown ({external_id})",
        )
        db.add(player)
        db.flush()
    elif team and player.team_id != team.id:
        player.team_id = team.id
    return player


def run_stats_ingestion(db: Session, connector: StatsConnector, game: Game) -> dict:
    source = connector.provider_name

    try:
        raw_team_stats = connector.fetch_team_stats(game.external_id)
        _log(db, source, "fetch_team_stats", "success", len(raw_team_stats))
    except Exception as e:
        _log(db, source, "fetch_team_stats", "error", 0, str(e))
        db.commit()
        raise

    team_stats_stored = 0
    for entry in raw_team_stats:
        team = _find_team(db, game.league_id, entry["team_external_id"], source)
        if not team:
            _log(db, source, "store_team_stats", "warning", 0, "unknown team, skipped")
            continue

        is_home = team.id == game.home_team_id
        existing_row = db.query(TeamGameStats).filter_by(game_id=game.id, team_id=team.id).first()
        if existing_row:
            existing_row.stats_json = entry["stats"]
            existing_row.is_home = is_home
        else:
            db.add(TeamGameStats(
                game_id=game.id, team_id=team.id, is_home=is_home, stats_json=entry["stats"],
            ))
        team_stats_stored += 1

    _log(db, source, "store_team_stats", "success", team_stats_stored)

    try:
        raw_player_stats = connector.fetch_player_stats(game.external_id)
        _log(db, source, "fetch_player_stats", "success", len(raw_player_stats))
    except Exception as e:
        _log(db, source, "fetch_player_stats", "error", 0, str(e))
        db.commit()
        raise

    player_stats_stored = 0
    for entry in raw_player_stats:
        team = None
        if entry.get("team_external_id"):
            team = _find_team(db, game.league_id, entry["team_external_id"], source)

        player = _get_or_create_player(db, team, entry["player_external_id"], entry["player_name"], source)

        existing_row = db.query(PlayerGameStats).filter_by(game_id=game.id, player_id=player.id).first()
        if existing_row:
            existing_row.stats_json = entry["stats"]
        else:
            db.add(PlayerGameStats(
                game_id=game.id,
                player_id=player.id,
                team_id=team.id if team else player.team_id,
                stats_json=entry["stats"],
            ))
        player_stats_stored += 1

    _log(db, source, "store_player_stats", "success", player_stats_stored)
    db.commit()

    return {
        "team_stats_stored": team_stats_stored,
        "player_stats_stored": player_stats_stored,
    }
