"""
BALLDONTLIE NFL connector.

Built to replace API-Sports for NFL specifically, after API-Sports'
free-tier NFL access was confirmed genuinely broken -- tested against
6 different season/date combinations, every single one returning a
"try this other range" error that then contradicted itself on the
very next call.

What's directly confirmed, not guessed:
- Base URL and endpoint path (https://api.balldontlie.io/nfl/v1/games)
- Free tier explicitly includes NFL games

What's INFERRED from the sibling NCAAF connector (same American-
football family, confirmed working) -- treat the first live call as
the real verification:
- "visitor_team" for the away side
- Flat home_score / away_score fields
- status_state using the shared cross-sport enum
- Team objects using "full_name" and "abbreviation"
"""

from typing import List, Dict, Any, Tuple, Optional

from app.ingestion.providers.balldontlie_base import BallDontLieBaseConnector, STATUS_STATE_MAP


class BallDontLieNFLConnector(BallDontLieBaseConnector):
    provider_name = "balldontlie_nfl"
    BASE_URL = "https://api.balldontlie.io/nfl/v1"

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
        away = raw.get("visitor_team")
        if raw.get("id") is None or home is None or away is None:
            return None

        status_state = raw.get("status_state", "unknown")

        return {
            "external_id": str(raw["id"]),
            "season": str(raw.get("season")),
            "game_date": raw.get("date"),
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
            "venue_name": None,
            "status": STATUS_STATE_MAP.get(status_state, "scheduled"),
            "home_score": raw.get("home_score"),
            "away_score": raw.get("away_score"),
        }
