"""
BALLDONTLIE NBA connector.

Confirmed against docs.balldontlie.io's "Get All Games" example
response, not guessed:
- Base URL: https://api.balldontlie.io/nba/v1
- Score fields are flat: home_team_score / visitor_team_score
- The away side is called "visitor_team", not "away_team"
- Team objects use "full_name" and "abbreviation"
- status_state present, shared cross-sport enum
"""

from typing import List, Dict, Any, Tuple, Optional

from app.ingestion.providers.balldontlie_base import BallDontLieBaseConnector, STATUS_STATE_MAP


class BallDontLieNBAConnector(BallDontLieBaseConnector):
    provider_name = "balldontlie_nba"
    BASE_URL = "https://api.balldontlie.io/nba/v1"

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
        away = raw.get("visitor_team")  # NBA calls it "visitor_team"
        if raw.get("id") is None or home is None or away is None:
            return None

        status_state = raw.get("status_state", "unknown")

        return {
            "external_id": str(raw["id"]),
            "season": str(raw.get("season")),
            "game_date": raw.get("datetime") or raw.get("date"),
            "home_team": {
                "external_id": str(home["id"]),
                "name": home.get("full_name"),
                "abbreviation": home.get("abbreviation"),
            },
            "away_team": {
                "external_id": str(away["id"]),
                "name": away.get("full_name"),
                "abbreviation": away.get("abbreviation"),
            },
            "venue_name": None,  # not provided by this endpoint
            "status": STATUS_STATE_MAP.get(status_state, "scheduled"),
            "home_score": raw.get("home_team_score"),
            "away_score": raw.get("visitor_team_score"),
        }
