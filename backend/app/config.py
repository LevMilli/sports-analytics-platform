"""
Centralized application settings.

Why this exists:
Every other module should read configuration from here rather than
calling os.environ directly. That way there is exactly one place that
knows how to find the database, decide whether to use the mock data
provider, etc. It also means secrets never get hardcoded into code.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+psycopg2://sports_admin:change_me_in_env@localhost:5432/sports_platform"
    redis_url: str = "redis://localhost:6379/0"

    use_mock_provider: bool = True
    api_sports_key: str = ""        # api-sports.io (API-NFL) — free tier, 100 req/day
    balldontlie_api_key: str = ""   # balldontlie.io (MLB/NBA/NHL/NCAAF) — free tier, 5 req/min
    sports_data_api_key: str = ""   # reserved for a future paid provider
    odds_api_key: str = ""          # reserved for The Odds API once we add odds in a later milestone

    log_level: str = "INFO"
    environment: str = "development"


# Import this singleton everywhere instead of instantiating Settings() again.
settings = Settings()
