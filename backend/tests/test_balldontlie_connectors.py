"""
Tests for the BALLDONTLIE connectors' mapping logic, using fixtures
taken verbatim from BALLDONTLIE's own docs/OpenAPI specs. No network
calls -- these verify the translation logic is correct before it ever
touches a real request or spends free-tier quota.
"""

from app.ingestion.providers.balldontlie_mlb_connector import BallDontLieMLBConnector
from app.ingestion.providers.balldontlie_nba_connector import BallDontLieNBAConnector
from app.ingestion.providers.balldontlie_nhl_connector import BallDontLieNHLConnector
from app.ingestion.providers.balldontlie_ncaaf_connector import BallDontLieNCAAFConnector


# --- MLB fixture, verbatim from mlb.balldontlie.io "Get All Games" example ---
MLB_GAME = {
    "id": 58590,
    "home_team_name": "New York Yankees",
    "away_team_name": "Los Angeles Dodgers",
    "home_team": {
        "id": 19, "slug": "new-york-yankees", "abbreviation": "NYY",
        "display_name": "New York Yankees", "short_display_name": "Yankees",
        "name": "Yankees", "location": "New York", "league": "American", "division": "East",
    },
    "away_team": {
        "id": 14, "slug": "los-angeles-dodgers", "abbreviation": "LAD",
        "display_name": "Los Angeles Dodgers", "short_display_name": "Dodgers",
        "name": "Dodgers", "location": "Los Angeles", "league": "National", "division": "West",
    },
    "season": 2024,
    "postseason": True,
    "season_type": "postseason",
    "date": "2024-10-30T00:08:00.000Z",
    "home_team_data": {"hits": 9, "runs": 11, "errors": 0, "inning_scores": [0, 1, 4, 0, 0, 1, 0, 5]},
    "away_team_data": {"hits": 6, "runs": 4, "errors": 1, "inning_scores": [2, 0, 0, 0, 2, 0, 0, 0, 0]},
    "venue": "Yankee Stadium",
    "attendance": 49354,
    "status": "STATUS_FINAL",
    "status_state": "final",
    "period": 9,
}


def test_mlb_mapping():
    mapped = BallDontLieMLBConnector._map_game(MLB_GAME)
    assert mapped["external_id"] == "58590"
    assert mapped["home_team"] == {"external_id": "19", "name": "New York Yankees", "abbreviation": "NYY"}
    assert mapped["away_team"] == {"external_id": "14", "name": "Los Angeles Dodgers", "abbreviation": "LAD"}
    assert mapped["home_score"] == 11  # runs, not hits
    assert mapped["away_score"] == 4
    assert mapped["status"] == "final"
    assert mapped["venue_name"] == "Yankee Stadium"


# --- NBA fixture, verbatim from docs.balldontlie.io "Get All Games" example ---
NBA_GAME = {
    "id": 15907925,
    "date": "2025-01-05",
    "season": 2024,
    "status": "Final",
    "status_state": "final",
    "period": 4,
    "postseason": False,
    "postponed": False,
    "home_team_score": 115,
    "visitor_team_score": 105,
    "datetime": "2025-01-05T23:00:00.000Z",
    "home_team": {"id": 6, "conference": "East", "division": "Central", "city": "Cleveland",
                  "name": "Cavaliers", "full_name": "Cleveland Cavaliers", "abbreviation": "CLE"},
    "visitor_team": {"id": 4, "conference": "East", "division": "Southeast", "city": "Charlotte",
                      "name": "Hornets", "full_name": "Charlotte Hornets", "abbreviation": "CHA"},
}


def test_nba_mapping():
    mapped = BallDontLieNBAConnector._map_game(NBA_GAME)
    assert mapped["external_id"] == "15907925"
    assert mapped["home_team"] == {"external_id": "6", "name": "Cleveland Cavaliers", "abbreviation": "CLE"}
    assert mapped["away_team"] == {"external_id": "4", "name": "Charlotte Hornets", "abbreviation": "CHA"}
    assert mapped["home_score"] == 115
    assert mapped["away_score"] == 105
    assert mapped["status"] == "final"


# --- NHL fixture, built from the confirmed OpenAPI schema fields ---
NHL_GAME = {
    "id": 987654,
    "season": 2025,
    "game_date": "2026-01-15",
    "start_time_utc": "2026-01-15T19:00:00.000Z",
    "home_team": {"id": 10, "full_name": "Toronto Maple Leafs", "tricode": "TOR",
                  "conference_name": "Eastern", "division_name": "Atlantic", "season": 2025},
    "away_team": {"id": 3, "full_name": "Boston Bruins", "tricode": "BOS",
                  "conference_name": "Eastern", "division_name": "Atlantic", "season": 2025},
    "home_score": 4,
    "away_score": 2,
    "venue": "Scotiabank Arena",
    "status_state": "final",
    "period": 3,
    "postseason": False,
}


def test_nhl_mapping():
    mapped = BallDontLieNHLConnector._map_game(NHL_GAME)
    assert mapped["external_id"] == "987654"
    assert mapped["home_team"] == {"external_id": "10", "name": "Toronto Maple Leafs", "abbreviation": "TOR"}
    assert mapped["away_team"] == {"external_id": "3", "name": "Boston Bruins", "abbreviation": "BOS"}
    assert mapped["home_score"] == 4
    assert mapped["away_score"] == 2
    assert mapped["status"] == "final"
    assert mapped["game_date"] == "2026-01-15T19:00:00.000Z"  # prefers start_time_utc


# --- NCAAF fixture, built from the confirmed OpenAPI schema fields ---
NCAAF_GAME = {
    "id": 457158,
    "date": "2026-09-13T17:00:00.000Z",
    "season": 2026,
    "week": 2,
    "status": "Final",
    "status_state": "final",
    "period": 4,
    "home_team": {"id": 55, "conference": "SEC", "city": "Athens", "name": "Bulldogs",
                  "full_name": "Georgia Bulldogs", "abbreviation": "UGA"},
    "visitor_team": {"id": 61, "conference": "ACC", "city": "Miami", "name": "Hurricanes",
                      "full_name": "Miami Hurricanes", "abbreviation": "MIA"},
    "home_score": 30,
    "away_score": 17,
}


def test_ncaaf_mapping():
    mapped = BallDontLieNCAAFConnector._map_game(NCAAF_GAME)
    assert mapped["external_id"] == "457158"
    assert mapped["home_team"] == {"external_id": "55", "name": "Georgia Bulldogs", "abbreviation": "UGA"}
    assert mapped["away_team"] == {"external_id": "61", "name": "Miami Hurricanes", "abbreviation": "MIA"}
    assert mapped["home_score"] == 30
    assert mapped["away_score"] == 17
    assert mapped["status"] == "final"


def test_all_connectors_reject_missing_teams():
    for cls, fixture in [
        (BallDontLieMLBConnector, MLB_GAME),
        (BallDontLieNBAConnector, NBA_GAME),
        (BallDontLieNHLConnector, NHL_GAME),
        (BallDontLieNCAAFConnector, NCAAF_GAME),
    ]:
        broken = {**fixture}
        # each sport uses a different key for the away side
        for key in ("away_team", "visitor_team"):
            if key in broken:
                broken[key] = None
        assert cls._map_game(broken) is None


def test_status_state_mapping_is_consistent_across_sports():
    from app.ingestion.providers.balldontlie_base import STATUS_STATE_MAP
    assert STATUS_STATE_MAP["in_progress"] == "live"
    assert STATUS_STATE_MAP["canceled"] == "cancelled"
    assert STATUS_STATE_MAP["final"] == "final"
    assert STATUS_STATE_MAP["scheduled"] == "scheduled"
