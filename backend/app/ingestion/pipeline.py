"""
Ingestion pipeline orchestrator.

Runs: fetch -> validate -> normalize/dedupe -> store -> log
for a single connector, league, and date range. This is deliberately
provider-agnostic -- swap MockProvider for a real connector later and
nothing else in this file changes.

Every stage writes an IngestionLog row so data-quality issues are
visible in the database rather than only in console output, matching
the "data quality monitoring" requirement from the project brief.
"""

from typing import Tuple
from sqlalchemy.orm import Session

from app.ingestion.base_connector import BaseConnector
from app.ingestion.validation import validate_games
from app.ingestion.normalization import normalize_and_dedupe_games
from app.db.models.core import Sport, League, Team, Game, IngestionLog


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _get_or_create_league(db: Session, sport_slug: str, sport_name: str,
                           league_slug: str, league_name: str) -> League:
    sport = db.query(Sport).filter_by(slug=sport_slug).first()
    if not sport:
        sport = Sport(name=sport_name, slug=sport_slug)
        db.add(sport)
        db.flush()

    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        league = League(sport_id=sport.id, name=league_name, slug=league_slug)
        db.add(league)
        db.flush()
    return league


def _get_or_create_team(db: Session, league: League, team_data: dict, provider: str) -> Team:
    team = db.query(Team).filter_by(
        league_id=league.id, external_id=team_data["external_id"], provider=provider
    ).first()
    if not team:
        team = Team(
            league_id=league.id,
            external_id=team_data["external_id"],
            provider=provider,
            name=team_data["name"],
            abbreviation=team_data.get("abbreviation"),
        )
        db.add(team)
        db.flush()
    return team


def run_game_ingestion(
    db: Session,
    connector: BaseConnector,
    sport_slug: str,
    sport_name: str,
    league_slug: str,
    league_name: str,
    date_range: Tuple[str, str],
) -> dict:
    """
    Runs the full pipeline once and returns a summary dict, e.g.:
    {"fetched": 4, "rejected": 1, "stored": 2, "duplicates_dropped": 1}
    """
    source = connector.provider_name

    # --- FETCH ---
    try:
        raw_records = connector.fetch_games(league_slug, date_range)
        _log(db, source, "fetch", "success", len(raw_records))
    except Exception as e:
        _log(db, source, "fetch", "error", 0, str(e))
        db.commit()
        raise

    # --- VALIDATE ---
    valid_records, rejected_records = validate_games(raw_records)
    _log(
        db, source, "validate",
        "success" if not rejected_records else "warning",
        len(valid_records),
        f"{len(rejected_records)} record(s) rejected: "
        + "; ".join(r["_rejection_reason"] for r in rejected_records) if rejected_records else "",
    )

    # --- NORMALIZE + DEDUPE ---
    before_dedupe = len(valid_records)
    normalized_records = normalize_and_dedupe_games(valid_records, source)
    duplicates_dropped = before_dedupe - len(normalized_records)
    _log(db, source, "normalize", "success", len(normalized_records),
         f"{duplicates_dropped} duplicate(s) dropped" if duplicates_dropped else "")

    # --- STORE ---
    league = _get_or_create_league(db, sport_slug, sport_name, league_slug, league_name)
    stored_count = 0
    for record in normalized_records:
        home_team = _get_or_create_team(db, league, record["home_team"], source)
        away_team = _get_or_create_team(db, league, record["away_team"], source)

        existing = db.query(Game).filter_by(
            league_id=league.id, external_id=record["external_id"], provider=source
        ).first()

        if existing:
            existing.status = record["status"]
            existing.home_score = record["home_score"]
            existing.away_score = record["away_score"]
        else:
            db.add(Game(
                league_id=league.id,
                external_id=record["external_id"],
                provider=source,
                season=record["season"],
                game_date=record["game_date"],
                home_team_id=home_team.id,
                away_team_id=away_team.id,
                venue_name=record["venue_name"],
                status=record["status"],
                home_score=record["home_score"],
                away_score=record["away_score"],
            ))
        stored_count += 1

    _log(db, source, "store", "success", stored_count)
    db.commit()

    return {
        "fetched": len(raw_records),
        "rejected": len(rejected_records),
        "duplicates_dropped": duplicates_dropped,
        "stored": stored_count,
    }
