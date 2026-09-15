"""
API-NFL connector (https://api-sports.io/documentation/nfl/v1).
League id 1 = NFL, confirmed stable across seasons per API-Sports docs.
"""

from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector


class ApiSportsConnector(ApiSportsBaseConnector):
    provider_name = "api_sports_nfl"
    BASE_URL = "https://v1.american-football.api-sports.io"
    LEAGUE_ID = 1
