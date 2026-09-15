"""
Tests for ApiSportsConnector's translation logic.

These use the exact example game object from API-Sports' own
documentation (the Broncos vs Bengals example) as a fixture, so we can
verify our mapping is correct without spending any of the free tier's
100 daily requests. No network calls happen in this file.
"""

from datetime import datetime
from app.ingestion.providers.api_sports_connector import ApiSportsConnector
from app.ingestion.providers.api_sports_base import season_for_date

# Taken verbatim from https://www.api-football.com's API-NFL guide,
# GET /games?id=17377
DOC_EXAMPLE_GAME = {
    "game": {
        "id": 17377,
        "stage": "Regular Season",
        "week": "Week 4",
        "date": {
            "timezone": "UTC",
            "date": "2025-09-30",
            "time": "00:15",
            "timestamp": 1759191300,
        },
        "venue": {"name": "Empower Field at Mile High", "city": "Denver"},
        "status": {"short": "FT", "long": "Finished", "timer": None},
    },
    "league": {
        "id": 1,
        "name": "NFL",
        "season": "2025",
        "logo": "https://media.api-sports.io/american-football/leagues/1.png",
        "country": {"name": "USA", "code": "US", "flag": "https://media.api-sports.io/flags/us.svg"},
    },
    "teams": {
        "home": {"id": 28, "name": "Denver Broncos", "logo": "https://media.api-sports.io/american-football/teams/28.png"},
        "away": {"id": 10, "name": "Cincinnati Bengals", "logo": "https://media.api-sports.io/american-football/teams/10.png"},
    },
    "scores": {
        "home": {"quarter_1": 7, "quarter_2": 14, "quarter_3": 0, "quarter_4": 7, "overtime": None, "total": 28},
        "away": {"quarter_1": 3, "quarter_2": 0, "quarter_3": 0, "quarter_4": 0, "overtime": None, "total": 3},
    },
}


def test_map_game_produces_common_shape():
    mapped = ApiSportsConnector._map_game(DOC_EXAMPLE_GAME, season=2025)

    assert mapped["external_id"] == "17377"
    assert mapped["season"] == "2025"
    assert mapped["game_date"] == "2025-09-30T00:15:00Z"
    assert mapped["venue_name"] == "Empower Field at Mile High"
    assert mapped["status"] == "final"  # FT -> final
    assert mapped["home_team"] == {"external_id": "28", "name": "Denver Broncos", "abbreviation": None}
    assert mapped["away_team"] == {"external_id": "10", "name": "Cincinnati Bengals", "abbreviation": None}
    assert mapped["home_score"] == 28
    assert mapped["away_score"] == 3


def test_map_game_handles_pregame_null_scores():
    pregame = {
        **DOC_EXAMPLE_GAME,
        "game": {**DOC_EXAMPLE_GAME["game"], "status": {"short": "NS", "long": "Not Started", "timer": None}},
        "scores": {
            "home": {"quarter_1": None, "quarter_2": None, "quarter_3": None, "quarter_4": None, "overtime": None, "total": None},
            "away": {"quarter_1": None, "quarter_2": None, "quarter_3": None, "quarter_4": None, "overtime": None, "total": None},
        },
    }
    mapped = ApiSportsConnector._map_game(pregame, season=2025)
    assert mapped["status"] == "scheduled"
    assert mapped["home_score"] is None
    assert mapped["away_score"] is None


def test_map_game_returns_none_for_missing_teams():
    broken = {**DOC_EXAMPLE_GAME, "teams": {"home": DOC_EXAMPLE_GAME["teams"]["home"], "away": None}}
    assert ApiSportsConnector._map_game(broken, season=2025) is None


def test_live_status_codes_map_to_live():
    for code in ["Q1", "Q2", "Q3", "Q4", "HT", "OT"]:
        live_game = {**DOC_EXAMPLE_GAME, "game": {**DOC_EXAMPLE_GAME["game"], "status": {"short": code, "long": "", "timer": None}}}
        mapped = ApiSportsConnector._map_game(live_game, season=2025)
        assert mapped["status"] == "live", f"expected {code} to map to live"


def test_season_for_date_regular_season_month():
    # September game -> season is the same year
    assert season_for_date(datetime(2025, 9, 30)) == 2025


def test_season_for_date_playoffs_belong_to_previous_year():
    # A January game is still part of the season that STARTED the previous year
    assert season_for_date(datetime(2026, 1, 15)) == 2025


def test_connector_requires_api_key():
    import pytest
    with pytest.raises(ValueError):
        ApiSportsConnector(api_key="")


def test_each_sport_connector_is_configured_correctly():
    """
    Every sport-specific connector must set a distinct provider_name,
    base_url, and league_id. This catches copy-paste mistakes (e.g.
    two sports accidentally sharing a league id) without hitting the
    network.
    """
    from app.ingestion.providers.api_sports_cfb_connector import ApiSportsCFBConnector
    from app.ingestion.providers.api_sports_mlb_connector import ApiSportsMLBConnector
    from app.ingestion.providers.api_sports_nhl_connector import ApiSportsNHLConnector
    from app.ingestion.providers.api_sports_nba_connector import ApiSportsNBAConnector

    connectors = [
        ApiSportsConnector(api_key="x"),
        ApiSportsCFBConnector(api_key="x"),
        ApiSportsMLBConnector(api_key="x"),
        ApiSportsNHLConnector(api_key="x"),
        ApiSportsNBAConnector(api_key="x"),
    ]

    provider_names = [c.provider_name for c in connectors]
    assert len(provider_names) == len(set(provider_names)), "duplicate provider_name across sports"

    # NFL and NCAA share a base URL (same API product) but must have
    # different league ids, or NCAA games would overwrite NFL games.
    assert ApiSportsConnector.BASE_URL == ApiSportsCFBConnector.BASE_URL
    assert ApiSportsConnector.LEAGUE_ID != ApiSportsCFBConnector.LEAGUE_ID

    # MLB, NHL, and NBA are each separate API products entirely.
    base_urls = [ApiSportsMLBConnector.BASE_URL, ApiSportsNHLConnector.BASE_URL,
                 ApiSportsNBAConnector.BASE_URL, ApiSportsConnector.BASE_URL]
    assert len(base_urls) == len(set(base_urls)), "two non-football sports share a base URL"
