"""
BALLDONTLIE MLB connector.

Confirmed against https://mlb.balldontlie.io/ (the exact "Get All
Games" example response), not guessed:
- Base URL: https://api.balldontlie.io/mlb/v1
- Games nest scores under home_team_data.runs / away_team_data.runs
  (MLB has hits/runs/errors, not a flat "score" field)
- Team objects use "display_name" (full) and "abbreviation"
- status_state is present and uses the shared cross-sport enum
"""

from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

from app.ingestion.providers.balldontlie_base import BallDontLieBaseConnector, STATUS_STATE_MAP


class BallDontLieMLBConnector(BallDontLieBaseConnector):
    provider_name = "balldontlie_mlb"
    BASE_URL = "https://api.balldontlie.io/mlb/v1"

    def fetch_games(self, league_slug: str, date_range: Tuple[str, str]) -> List[Dict[str, Any]]:
        start, end = date_range
        dates = self._daterange(start, end)

        raw_games = self._get_all_pages("/games", {"dates[]": dates})

        games = []
        for raw in raw_games:
            mapped = self._map_game(raw)
            if mapped is not None:
                games.append(mapped)
        return games

    @staticmethod
    def _map_game(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        home = raw.get("home_team")
        away = raw.get("away_team")
        if raw.get("id") is None or home is None or away is None:
            return None

        home_data = raw.get("home_team_data") or {}
        away_data = raw.get("away_team_data") or {}
        status_state = raw.get("status_state", "unknown")

        return {
            "external_id": str(raw["id"]),
            "season": str(raw.get("season")),
            "game_date": raw.get("date"),  # already ISO 8601
            "home_team": {
                "external_id": str(home["id"]),
                "name": home.get("display_name"),
                "abbreviation": home.get("abbreviation"),
            },
            "away_team": {
                "external_id": str(away["id"]),
                "name": away.get("display_name"),
                "abbreviation": away.get("abbreviation"),
            },
            "venue_name": raw.get("venue"),
            "status": STATUS_STATE_MAP.get(status_state, "scheduled"),
            "home_score": home_data.get("runs"),
            "away_score": away_data.get("runs"),
        }
