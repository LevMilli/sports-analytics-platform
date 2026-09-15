"""
Shared base connector for BALLDONTLIE's per-sport APIs.

Why this exists:
Unlike API-Sports, BALLDONTLIE's sports genuinely differ in response
shape (MLB nests scores under home_team_data/away_team_data; NBA and
NCAAF use "visitor_team" instead of "away_team"; NHL uses "game_date"
instead of "date"). Rather than force a fake common shape, this base
class only handles what really is identical across all of
BALLDONTLIE's sports: auth, HTTP, and error handling. Each sport's
connector owns its own _map_game translation.

Confirmed directly against BALLDONTLIE's own OpenAPI specs and docs
pages (not guessed):
- Auth header: "Authorization: <key>" (no "Bearer" prefix)
- Base URL pattern: https://api.balldontlie.io/<sport>/v1
- Games endpoint accepts a `dates[]` array parameter -- multiple dates
  can be requested in a single call, unlike API-Sports which required
  one request per day
- Free tier explicitly includes the Games endpoint for every sport
  (confirmed in both the NBA and MLB account-tier tables)
"""

from typing import Dict, Any, List

import httpx


class BallDontLieBaseConnector:
    BASE_URL: str = ""  # set per sport, e.g. "https://api.balldontlie.io/mlb/v1"
    provider_name: str = "balldontlie_base"

    def __init__(self, api_key: str, timeout: float = 10.0):
        if not self.BASE_URL:
            raise NotImplementedError(f"{type(self).__name__} must set BASE_URL")
        if not api_key:
            raise ValueError(
                f"{type(self).__name__} requires an API key. "
                "Sign up free at https://app.balldontlie.io and set "
                "BALLDONTLIE_API_KEY in backend/.env"
            )
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": self.api_key}

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{path}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(), params=params)

        if resp.status_code == 401:
            raise RuntimeError(f"{self.provider_name} 401: API key missing/invalid or tier lacks access.")
        if resp.status_code == 429:
            raise RuntimeError(f"{self.provider_name} 429: rate limit hit, back off and retry later.")
        if resp.status_code >= 500:
            raise RuntimeError(f"{self.provider_name} {resp.status_code}: server error, retry once after a short wait.")
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _daterange(start: str, end: str) -> List[str]:
        from datetime import datetime, timedelta
        start_d = datetime.strptime(start, "%Y-%m-%d")
        end_d = datetime.strptime(end, "%Y-%m-%d")
        days = []
        d = start_d
        while d <= end_d:
            days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return days


# Shared status_state -> our vocabulary mapping. Confirmed identical
# across BALLDONTLIE's NBA, MLB, NHL, and NCAAF OpenAPI specs
# (the CompetitionStatusState enum is copy-identical in all of them).
STATUS_STATE_MAP = {
    "scheduled": "scheduled",
    "in_progress": "live",
    "final": "final",
    "postponed": "postponed",
    "canceled": "cancelled",
    "delayed": "live",
    "suspended": "live",
    "abandoned": "final",
    "unknown": "scheduled",
}
