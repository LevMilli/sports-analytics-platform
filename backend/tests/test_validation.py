from app.ingestion.validation import validate_games
from app.ingestion.providers.mock_provider import MockProvider


def test_valid_games_pass():
    records = MockProvider().fetch_games("mock-league", ("2026-01-01", "2026-01-01"))
    valid, rejected = validate_games(records)
    # The mock provider ships 4 records: 2 good, 1 malformed, 1 duplicate
    # of a good one. Duplicates are still individually "valid" -- dedupe
    # happens at normalization, not validation.
    assert len(valid) == 3
    assert len(rejected) == 1
    assert "away_team" in rejected[0]["_rejection_reason"]


def test_identical_home_and_away_rejected():
    records = [{
        "external_id": "X1",
        "game_date": "2026-01-01T00:00:00Z",
        "home_team": {"external_id": "TEAM-A", "name": "A"},
        "away_team": {"external_id": "TEAM-A", "name": "A"},
    }]
    valid, rejected = validate_games(records)
    assert len(valid) == 0
    assert len(rejected) == 1
