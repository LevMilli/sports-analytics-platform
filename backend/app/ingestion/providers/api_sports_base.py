"""
Generic base connector for API-Sports' family of per-sport APIs
(American Football, Baseball, Hockey, Basketball, etc.)

Why this exists:
API-Sports runs each sport as a SEPARATE product (separate base URL,
separate free-tier quota of 100 requests/day) but all of them share
the same auth scheme, response envelope, and games/teams/scores JSON
shape -- confirmed against their American Football and Baseball docs.
Rather than copy-pasting the same HTTP/mapping logic once per sport,
each sport gets a thin subclass that only sets base_url, league_id,
and provider_name. If a specific sport's API turns out to diverge
from this shape, override _map_game in that sport's subclass rather
than bending this base class.

One league id is NOT universal across sports -- each sport API has
its own id space (NFL=1/NCAA=2 on the football API, MLB=1 on the
baseball API, NHL=57 on the hockey API). These were pulled from
API-Sports' own documented example responses, not guessed. Always
confirm a new league id with GET /leagues before hardcoding it.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

import httpx

from app.ingestion.base_connector import BaseConnector

STATUS_MAP = {
    "NS": "scheduled",
    "Q1": "live", "Q2": "live", "Q3": "live", "Q4": "live",
    "HT": "live", "OT": "live",
    "FT": "final", "AOT": "final",
    "CANC": "cancelled",
    "PST": "postponed",
}


def season_for_date(d: datetime) -> int:
    return d.year if d.month >= 3 else d.year - 1


class ApiSportsBaseConnector(BaseConnector):
    BASE_URL: str = ""
    LEAGUE_ID: int = 0
    provider_name: str = "api_sports_base"

    def __init__(self, api_key: str, timeout: float = 10.0):
        if not self.BASE_URL or not self.LEAGUE_ID:
            raise NotImplementedError(
                f"{type(self).__name__} must set BASE_URL and LEAGUE_ID"
            )
        if not api_key:
            raise ValueError(
                f"{type(self).__name__} requires an API key. "
                "Sign up free at https://dashboard.api-football.com/register "
                "and set API_SPORTS_KEY in backend/.env"
            )
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {"x-apisports-key": self.api_key}

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params)

        if resp.status_code == 403:
            raise RuntimeError(f"{self.provider_name} 403: API key missing or invalid.")
        if resp.status_code == 429:
            raise RuntimeError(f"{self.provider_name} 429: rate limit hit, back off and retry later.")
        if resp.status_code >= 500:
            raise RuntimeError(f"{self.provider_name} {resp.status_code}: server error, retry once after a short wait.")
        resp.raise_for_status()

        data = resp.json()
        errors = data.get("errors")
        if errors:
            raise RuntimeError(f"{self.provider_name} returned errors: {errors}")
        return data

    def _daterange(self, start: str, end: str) -> List[str]:
        start_d = datetime.strptime(start, "%Y-%m-%d")
        end_d = datetime.strptime(end, "%Y-%m-%d")
        days = []
        d = start_d
        while d <= end_d:
            days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return days

    def fetch_games(self, league_slug: str, date_range: Tuple[str, str]) -> List[Dict[str, Any]]:
        start, end = date_range
        season = season_for_date(datetime.strptime(start, "%Y-%m-%d"))

        games: List[Dict[str, Any]] = []
        for day in self._daterange(start, end):
            data = self._get("/games", {
                "league": self.LEAGUE_ID,
                "season": season,
                "date": day,
            })
            for raw in data.get("response", []):
                mapped = self._map_game(raw, season)
                if mapped is not None:
                    games.append(mapped)
        return games

    def fetch_team_stats(self, game_external_id: str) -> List[Dict[str, Any]]:
        data = self._get("/games/statistics/teams", {"id": game_external_id})
        return self._map_team_stats_response(data)

    def fetch_player_stats(self, game_external_id: str) -> List[Dict[str, Any]]:
        data = self._get("/games/statistics/players", {"id": game_external_id})
        return self._map_player_stats_response(data)

    def fetch_injuries(self, team_external_id: str) -> List[Dict[str, Any]]:
        data = self._get("/injuries", {"team": team_external_id})
        return self._map_injuries_response(data)

    @staticmethod
    def _map_injuries_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for entry in data.get("response", []):
            player = entry.get("player") or {}
            if player.get("id") is None:
                continue
            results.append({
                "player_external_id": str(player["id"]),
                "player_name": player.get("name"),
                "status": (entry.get("status") or "unknown").lower(),
                "description": entry.get("description"),
                "report_date": entry.get("date"),
            })
        return results

    @staticmethod
    def _map_team_stats_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for entry in data.get("response", []):
            team = entry.get("team") or {}
            if team.get("id") is None:
                continue
            results.append({
                "team_external_id": str(team["id"]),
                "team_name": team.get("name"),
                "stats": entry.get("statistics"),
            })
        return results

    @staticmethod
    def _map_player_stats_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        for group in data.get("response", []):
            team = group.get("team") or {}
            for player_entry in group.get("players", []):
                player = player_entry.get("player") or {}
                if player.get("id") is None:
                    continue
                results.append({
                    "player_external_id": str(player["id"]),
                    "player_name": player.get("name"),
                    "team_external_id": str(team["id"]) if team.get("id") is not None else None,
                    "stats": player_entry.get("statistics"),
                })
        return results

    @staticmethod
    def _map_game(raw: Dict[str, Any], season: int) -> Optional[Dict[str, Any]]:
        game = raw.get("game", {})
        teams = raw.get("teams", {})
        scores = raw.get("scores", {})
        home = teams.get("home")
        away = teams.get("away")

        if game.get("id") is None or home is None or away is None:
            return None

        date_obj = game.get("date", {})
        date_str = date_obj.get("date")
        time_str = date_obj.get("time", "00:00")
        game_date_iso = f"{date_str}T{time_str}:00Z" if date_str else None

        status_short = (game.get("status") or {}).get("short", "NS")

        return {
            "external_id": str(game["id"]),
            "season": str(season),
            "game_date": game_date_iso,
            "home_team": {
                "external_id": str(home["id"]),
                "name": home.get("name"),
                "abbreviation": None,
            },
            "away_team": {
                "external_id": str(away["id"]),
                "name": away.get("name"),
                "abbreviation": None,
            },
            "venue_name": (game.get("venue") or {}).get("name"),
            "status": STATUS_MAP.get(status_short, "scheduled"),
            "home_score": (scores.get("home") or {}).get("total"),
            "away_score": (scores.get("away") or {}).get("total"),
        }
