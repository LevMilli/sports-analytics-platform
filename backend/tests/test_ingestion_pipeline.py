"""
End-to-end test of the ingestion pipeline: fetch -> validate ->
normalize -> dedupe -> store -> log, run against the mock provider.

This is the test that proves the pipeline is safe to point at a real
data source later: correct records land in the DB, bad records are
rejected and logged (not silently dropped), duplicates don't create
duplicate rows, and re-running ingestion is idempotent (upsert, not
duplicate insert).
"""

from app.ingestion.providers.mock_provider import MockProvider
from app.ingestion.pipeline import run_game_ingestion
from app.db.models.core import Game, Team, IngestionLog


def _run(db_session):
    return run_game_ingestion(
        db=db_session,
        connector=MockProvider(),
        sport_slug="basketball",
        sport_name="Basketball",
        league_slug="mock-league",
        league_name="Mock Test League",
        date_range=("2026-01-01", "2026-01-01"),
    )


def test_pipeline_stores_only_valid_deduped_games(db_session):
    result = _run(db_session)

    assert result["fetched"] == 4
    assert result["rejected"] == 1
    assert result["duplicates_dropped"] == 1
    assert result["stored"] == 2

    games = db_session.query(Game).all()
    assert len(games) == 2

    teams = db_session.query(Team).all()
    # 4 distinct teams across the 2 stored games
    assert len(teams) == 4


def test_pipeline_is_idempotent_on_rerun(db_session):
    _run(db_session)
    _run(db_session)  # run again -- should upsert, not duplicate

    games = db_session.query(Game).all()
    assert len(games) == 2, "re-running ingestion created duplicate game rows"


def test_pipeline_writes_ingestion_logs(db_session):
    _run(db_session)
    logs = db_session.query(IngestionLog).all()
    stages = {log.stage for log in logs}
    assert {"fetch", "validate", "normalize", "store"}.issubset(stages)

    validate_log = next(log for log in logs if log.stage == "validate")
    assert validate_log.status == "warning"  # because 1 record was rejected
    assert "away_team" in validate_log.message
