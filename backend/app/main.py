"""
FastAPI application entrypoint.
"""

from datetime import date
from typing import Type, Union

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db, engine, Base
from app.db import models  # noqa: F401
from app.config import settings
from app.ingestion.providers.mock_provider import MockProvider
from app.ingestion.providers.api_sports_base import ApiSportsBaseConnector
from app.ingestion.providers.api_sports_connector import ApiSportsConnector
from app.ingestion.providers.balldontlie_base import BallDontLieBaseConnector
from app.ingestion.providers.balldontlie_nfl_connector import BallDontLieNFLConnector
from app.ingestion.providers.balldontlie_mlb_connector import BallDontLieMLBConnector
from app.ingestion.providers.balldontlie_nba_connector import BallDontLieNBAConnector
from app.ingestion.providers.balldontlie_nhl_connector import BallDontLieNHLConnector
from app.ingestion.providers.balldontlie_ncaaf_connector import BallDontLieNCAAFConnector
from app.ingestion.pipeline import run_game_ingestion
from app.ingestion.stats_pipeline import run_stats_ingestion
from app.ingestion.injury_pipeline import run_injury_ingestion
from app.features.feature_pipeline import compute_features_for_league
from app.features.elo_pipeline import compute_elo_for_league
from app.features.backtest_pipeline import run_backtest_for_league
from app.features.explain_pipeline import explain_game
from app.features.logistic_pipeline import train_logistic_for_league
from app.features.alerts_pipeline import generate_alerts_for_league
from app.features.games_list import list_games_for_league
from app.db.models.core import Game, League, Team, Alert

app = FastAPI(title="Sports Data Analysis Platform", version="0.1.0-mvp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    if settings.environment == "development":
        Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "environment": settings.environment}


@app.post("/ingestion/test-run")
def trigger_test_ingestion(db: Session = Depends(get_db)):
    connector = MockProvider()
    result = run_game_ingestion(
        db=db,
        connector=connector,
        sport_slug="basketball",
        sport_name="Basketball",
        league_slug="mock-league",
        league_name="Mock Test League",
        date_range=("2026-01-01", "2026-01-01"),
    )
    return {"provider": connector.provider_name, "result": result}


def _run_sync(connector, sport_slug, sport_name, league_slug, league_name, start, end, db):
    try:
        result = run_game_ingestion(
            db=db,
            connector=connector,
            sport_slug=sport_slug,
            sport_name=sport_name,
            league_slug=league_slug,
            league_name=league_name,
            date_range=(start, end),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {"provider": connector.provider_name, "date_range": [start, end], "result": result}


def _sync_via_api_sports(connector_cls, sport_slug, sport_name, league_slug, league_name, start, end, db):
    if not settings.api_sports_key:
        raise HTTPException(
            status_code=400,
            detail="API_SPORTS_KEY is not set. Sign up free at https://dashboard.api-football.com/register, grab your key from Account -> My Access, and set it in backend/.env, then restart the stack.",
        )
    end = end or start
    connector = connector_cls(api_key=settings.api_sports_key)
    return _run_sync(connector, sport_slug, sport_name, league_slug, league_name, start, end, db)


def _sync_via_balldontlie(connector_cls, sport_slug, sport_name, league_slug, league_name, start, end, db):
    if not settings.balldontlie_api_key:
        raise HTTPException(
            status_code=400,
            detail="BALLDONTLIE_API_KEY is not set. Sign up free at https://app.balldontlie.io, grab your key from Account Settings, and set it in backend/.env, then restart the stack.",
        )
    end = end or start
    connector = connector_cls(api_key=settings.balldontlie_api_key)
    return _run_sync(connector, sport_slug, sport_name, league_slug, league_name, start, end, db)


_START_Q = Query(default_factory=lambda: date.today().isoformat(), description="YYYY-MM-DD")
_END_Q = Query(default=None, description="YYYY-MM-DD, defaults to start")


@app.post("/ingestion/nfl/sync")
def sync_nfl_games(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    return _sync_via_balldontlie(BallDontLieNFLConnector, "football", "American Football", "nfl", "NFL", start, end, db)


@app.post("/ingestion/cfb/sync")
def sync_cfb_games(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    return _sync_via_balldontlie(BallDontLieNCAAFConnector, "football", "American Football", "ncaaf", "NCAA Football", start, end, db)


@app.post("/ingestion/mlb/sync")
def sync_mlb_games(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    return _sync_via_balldontlie(BallDontLieMLBConnector, "baseball", "Baseball", "mlb", "MLB", start, end, db)


@app.post("/ingestion/nhl/sync")
def sync_nhl_games(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    return _sync_via_balldontlie(BallDontLieNHLConnector, "hockey", "Hockey", "nhl", "NHL", start, end, db)


@app.post("/ingestion/nba/sync")
def sync_nba_games(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    return _sync_via_balldontlie(BallDontLieNBAConnector, "basketball", "Basketball", "nba", "NBA", start, end, db)


@app.post("/ingestion/nfl/stats/sync")
def sync_nfl_stats(start: str = _START_Q, end: str = _END_Q, db: Session = Depends(get_db)):
    if not settings.api_sports_key:
        raise HTTPException(status_code=400, detail="API_SPORTS_KEY is not set. See the /ingestion/nfl/sync error for setup steps.")

    league = db.query(League).filter_by(slug="nfl").first()
    if not league:
        raise HTTPException(status_code=400, detail="No 'nfl' league found yet -- run /ingestion/nfl/sync at least once first so there are games on file to fetch stats for.")

    end = end or start
    games = (
        db.query(Game)
        .filter(
            Game.league_id == league.id,
            Game.provider == "api_sports_nfl",
            Game.game_date >= f"{start}T00:00:00Z",
            Game.game_date <= f"{end}T23:59:59Z",
        )
        .all()
    )
    if not games:
        raise HTTPException(status_code=404, detail=f"No NFL games on file between {start} and {end}. Run /ingestion/nfl/sync for that range first.")

    connector = ApiSportsConnector(api_key=settings.api_sports_key)
    per_game_results = {}
    for game in games:
        try:
            per_game_results[game.external_id] = run_stats_ingestion(db, connector, game)
        except RuntimeError as e:
