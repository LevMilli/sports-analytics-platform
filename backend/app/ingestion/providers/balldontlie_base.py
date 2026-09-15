"""
Shared base connector for BALLDONTLIE's per-sport APIs.
"""

from typing import Dict, Any, List

import httpx


class BallDontLieBaseConnector:
    BASE_URL: str = ""
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

    def _get_all_pages(self, path: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        all_data: List[Dict[str, Any]] = []
        page_params = dict(params)
        page_params["per_page"] = 100
        cursor = None

        while True:
            if cursor is not None:
                page_params["cursor"] = cursor
            page = self._get(path, page_params)
            all_data.extend(page.get("data", []))
            meta = page.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not cursor:
                break

        return all_data

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
