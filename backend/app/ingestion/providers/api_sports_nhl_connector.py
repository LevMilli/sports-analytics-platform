"""
API-Hockey connector (https://api-sports.io/documentation/hockey/v1).
League id 57 = NHL, confirmed via API-Sports' /leagues endpoint (not
a guess -- Hockey's league ids are not sequential like Football's).

This is a SEPARATE API-Sports product from API-NFL/API-Baseball, with
its own 100 requests/day free-tier quota. Same account/API key works
across all of API-Sports' products, per their docs.
"""

from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector


class ApiSportsNHLConnector(ApiSportsBaseConnector):
    provider_name = "api_sports_nhl"
    BASE_URL = "https://v1.hockey.api-sports.io"
    LEAGUE_ID = 57
