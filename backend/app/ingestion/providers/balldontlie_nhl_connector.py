"""
BALLDONTLIE NHL connector.

Confirmed against https://www.balldontlie.io/openapi/nhl.yml (the
authoritative OpenAPI spec), not guessed:
- Base URL: https://api.balldontlie.io/nhl/v1
- Score fields are flat: home_score / away_score
- The date field is called "game_date", not "date"
- Team objects use "full_name" and "tricode" (their abbreviation)
- status_state present, shared cross-sport enum
"""

from typing import List, Dict, Any, Tuple, Optional

from app.ingestion.providers.balldontlie_base import BallDontLieBaseConnector, STATUS_STATE_MAP


class BallDontLieNHLConnector(BallDontLieBaseConnector):
    provider_name = "balldontlie_nhl"
    BASE_URL = "https://api.balldontlie.io/nhl/v1"

    def fetch_games(self, league_slug: str, date_range: Tuple[str, str]) -> List[Dict[str, Any]]:
        start, end = date_range
        dates = self._daterange(start, end)

        data = self._get("/games", {"dates[]": dates})

        games = []
        for raw in data.get("data", []):
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

        status_state = raw.get("status_state", "unknown")
        game_date = raw.get("start_time_utc") or raw.get("game_date")

        return {
            "external_id": str(raw["id"]),
            "season": str(raw.get("season")),
            "game_date": game_date,
            "home_team": {
                "external_id": str(home["id"]),
                "name": home.get("full_name"),
                "abbreviation": home.get("tricode"),
            },
            "away_team": {
                "external_id": str(away["id"]),
                "name": away.get("full_name"),
                "abbreviation": away.get("tricode"),
            },
            "venue_name": raw.get("venue"),
            "status": STATUS_STATE_MAP.get(status_state, "scheduled"),
            "home_score": raw.get("home_score"),
            "away_score": raw.get("away_score"),
        }
