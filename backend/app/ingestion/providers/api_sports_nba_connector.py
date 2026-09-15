"""
API-Basketball connector (https://api-sports.io/documentation/basketball/v1).
League id 12 = NBA, confirmed via API-Sports' own documented /leagues
example response ("id": 12, "name": "NBA", "country": {"name": "USA"}).

Separate API-Sports product from Football/Baseball/Hockey, with its
own 100 requests/day free-tier quota. Same account/API key works
across all of them, per API-Sports docs.
"""

from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector


class ApiSportsNBAConnector(ApiSportsBaseConnector):
    provider_name = "api_sports_nba"
    BASE_URL = "https://v1.basketball.api-sports.io"
    LEAGUE_ID = 12
