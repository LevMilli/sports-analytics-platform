"""
Mock provider used to test the ingestion pipeline before any real,
authorized data source is wired up.

Why this exists:
We want to prove the pipeline (fetch -> validate -> normalize ->
dedupe -> store -> log) works correctly, is idempotent, and handles
bad records gracefully -- all before spending time on real API
integration or touching a live/paid data source. This connector
returns deterministic, clearly-fake data (team/player names are
obviously placeholders) so it can never be mistaken for real sports
data downstream.

It also deliberately includes a couple of "bad" records (missing
field, duplicate) so the validation and dedupe stages have something
real to catch during testing.
"""

from typing import List, Dict, Any
from app.ingestion.base_connector import BaseConnector


class MockProvider(BaseConnector):
    provider_name = "mock_test_provider"

    def fetch_games(self, league_slug: str, date_range: tuple[str, str]) -> List[Dict[str, Any]]:
        start, _end = date_range

        games = [
            {
                "external_id": "MOCK-GAME-1",
                "season": "2025-2026",
                "game_date": f"{start}T19:00:00Z",
                "home_team": {"external_id": "MOCK-TEAM-A", "name": "Test City Falcons", "abbreviation": "TCF"},
                "away_team": {"external_id": "MOCK-TEAM-B", "name": "Sample Town Comets", "abbreviation": "STC"},
                "venue_name": "Mock Arena",
                "status": "final",
                "home_score": 101,
                "away_score": 97,
            },
            {
                "external_id": "MOCK-GAME-2",
                "season": "2025-2026",
                "game_date": f"{start}T21:30:00Z",
                "home_team": {"external_id": "MOCK-TEAM-C", "name": "Placeholder United", "abbreviation": "PLU"},
                "away_team": {"external_id": "MOCK-TEAM-D", "name": "Fixture Athletic", "abbreviation": "FXA"},
                "venue_name": "Demo Stadium",
                "status": "scheduled",
                "home_score": None,
                "away_score": None,
            },
            # Intentionally malformed record: missing away_team.
            # This exists so the validation stage has something to reject
            # during testing -- it should never reach the database.
            {
                "external_id": "MOCK-GAME-3-BAD",
                "season": "2025-2026",
                "game_date": f"{start}T23:00:00Z",
                "home_team": {"external_id": "MOCK-TEAM-A", "name": "Test City Falcons", "abbreviation": "TCF"},
                "away_team": None,
                "venue_name": "Mock Arena",
                "status": "scheduled",
                "home_score": None,
                "away_score": None,
            },
            # Intentional duplicate of GAME-1 to test dedupe logic.
            {
                "external_id": "MOCK-GAME-1",
                "season": "2025-2026",
                "game_date": f"{start}T19:00:00Z",
                "home_team": {"external_id": "MOCK-TEAM-A", "name": "Test City Falcons", "abbreviation": "TCF"},
                "away_team": {"external_id": "MOCK-TEAM-B", "name": "Sample Town Comets", "abbreviation": "STC"},
                "venue_name": "Mock Arena",
                "status": "final",
                "home_score": 101,
                "away_score": 97,
            },
        ]
        return games
