from app.ingestion.validation import validate_games
from app.ingestion.normalization import normalize_and_dedupe_games
from app.ingestion.providers.mock_provider import MockProvider


def test_dedupe_drops_repeated_external_id():
    records = MockProvider().fetch_games("mock-league", ("2026-01-01", "2026-01-01"))
    valid, _rejected = validate_games(records)
    normalized = normalize_and_dedupe_games(valid, provider="mock_test_provider")

    external_ids = [r["external_id"] for r in normalized]
    assert len(external_ids) == len(set(external_ids)), "duplicate external_id made it through"
    assert len(normalized) == 2  # MOCK-GAME-1 (deduped) and MOCK-GAME-2


def test_game_date_is_parsed_to_datetime():
    records = MockProvider().fetch_games("mock-league", ("2026-01-01", "2026-01-01"))
    valid, _ = validate_games(records)
    normalized = normalize_and_dedupe_games(valid, provider="mock_test_provider")
    for record in normalized:
        assert record["game_date"].year == 2026
