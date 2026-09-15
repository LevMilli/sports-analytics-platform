"""
API-Baseball connector (https://api-sports.io/documentation/baseball/v1).
League id 1 = MLB, confirmed via API-Sports' own documented example
response ("league": {"id": 1, "name": "MLB", ...}).

This is a SEPARATE API-Sports product from API-NFL, with its own
100 requests/day free-tier quota -- your NFL usage doesn't eat into
this one. Same account/API key works across both, per API-Sports docs.
"""

from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector


class ApiSportsMLBConnector(ApiSportsBaseConnector):
    provider_name = "api_sports_mlb"
    BASE_URL = "https://v1.baseball.api-sports.io"
    LEAGUE_ID = 1
