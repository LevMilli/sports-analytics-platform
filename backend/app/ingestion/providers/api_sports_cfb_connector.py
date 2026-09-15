"""
API-NFL's NCAA competition (same base URL and API as NFL, different
league id). League id 2 = NCAA, confirmed via API-Sports' API-NFL docs
("NFL is always 1 and NCAA is always 2").

Uses the same API_SPORTS_KEY as the NFL connector -- one account
covers both competitions on this API product.
"""

from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector


class ApiSportsCFBConnector(ApiSportsBaseConnector):
    provider_name = "api_sports_ncaaf"
    BASE_URL = "https://v1.american-football.api-sports.io"
    LEAGUE_ID = 2
