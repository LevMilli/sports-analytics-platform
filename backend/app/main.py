"""
FastAPI application entrypoint.
"""

from datetime import date
from typing import Type, Union

from fastapi import FastAPI, Depends, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
from app.features.auth_pipeline import sign_up, log_in, log_out, get_current_user, update_profile, deactivate_account
from app.db.models.core import Game, League, Team, Alert, PredictionSnapshot

app = FastAPI(title="Sports Data Analysis Platform", version="0.1.0-mvp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sports-analytics-platform-1-eoln.onrender.com", "http://localhost:5500", "http://localhost:5501"],
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
            per_game_results[game.external_id] = {"error": str(e)}

    return {"provider": connector.provider_name, "date_range": [start, end], "games_processed": len(games), "results": per_game_results}


@app.post("/ingestion/nfl/injuries/sync")
def sync_nfl_injuries(db: Session = Depends(get_db)):
    if not settings.api_sports_key:
        raise HTTPException(status_code=400, detail="API_SPORTS_KEY is not set. See the /ingestion/nfl/sync error for setup steps.")

    league = db.query(League).filter_by(slug="nfl").first()
    if not league:
        raise HTTPException(status_code=400, detail="No 'nfl' league found yet -- run /ingestion/nfl/sync at least once first so there are teams on file to fetch injuries for.")

    teams = db.query(Team).filter_by(league_id=league.id, provider="api_sports_nfl").all()
    if not teams:
        raise HTTPException(status_code=404, detail="No NFL teams on file yet. Run /ingestion/nfl/sync first.")

    connector = ApiSportsConnector(api_key=settings.api_sports_key)
    per_team_results = {}
    for team in teams:
        try:
            per_team_results[team.name] = run_injury_ingestion(db, connector, team)
        except RuntimeError as e:
            per_team_results[team.name] = {"error": str(e)}

    return {"provider": connector.provider_name, "teams_processed": len(teams), "results": per_team_results}


@app.post("/features/nfl/compute")
def compute_nfl_features(db: Session = Depends(get_db)):
    try:
        result = compute_features_for_league(db, "nfl")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.post("/features/nfl/elo/compute")
def compute_nfl_elo(db: Session = Depends(get_db)):
    try:
        result = compute_elo_for_league(db, "nfl")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.post("/backtest/nfl/run")
def backtest_nfl(model: str = "elo", db: Session = Depends(get_db)):
    try:
        result = run_backtest_for_league(db, "nfl", model_name=model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/games/{game_id}/explain")
def explain_game_endpoint(game_id: int, db: Session = Depends(get_db)):
    try:
        result = explain_game(db, game_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return result


@app.get("/games/{game_id}/history")
def game_history_endpoint(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter_by(id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail=f"No game found with id {game_id}")

    snapshots = (
        db.query(PredictionSnapshot)
        .filter_by(game_id=game_id, team_id=game.home_team_id)
        .order_by(PredictionSnapshot.recorded_at.asc())
        .all()
    )

    return {
        "game_id": game_id,
        "points": [
            {
                "model_name": s.model_name,
                "win_probability": float(s.win_probability),
                "recorded_at": s.recorded_at.isoformat() if s.recorded_at else None,
            }
            for s in snapshots
        ],
    }


@app.post("/features/nfl/logistic/train")
def train_nfl_logistic(db: Session = Depends(get_db)):
    try:
        result = train_logistic_for_league(db, "nfl")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.post("/alerts/nfl/generate")
def generate_nfl_alerts(db: Session = Depends(get_db)):
    try:
        result = generate_alerts_for_league(db, "nfl")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.get("/alerts/nfl")
def list_nfl_alerts(db: Session = Depends(get_db)):
    league = db.query(League).filter_by(slug="nfl").first()
    if not league:
        return {"alerts": []}

    alerts = db.query(Alert).filter_by(league_id=league.id).order_by(Alert.created_at.desc()).all()
    return {
        "alerts": [
            {
                "game_id": a.game_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "message": a.message,
            }
            for a in alerts
        ]
    }


@app.get("/games/{league_slug}")
def list_league_games(league_slug: str, status: str = None, limit: int = 50, db: Session = Depends(get_db)):
    try:
        result = list_games_for_league(db, league_slug, status=status, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


@app.post("/admin/seed-demo-data")
def seed_demo_data(db: Session = Depends(get_db)):
    import random
    from datetime import datetime, timezone, timedelta
    from app.db.models.core import Sport, League, Team, Game

    sport = db.query(Sport).filter_by(slug="football").first()
    if not sport:
        sport = Sport(name="Football", slug="football")
        db.add(sport)
        db.flush()

    league = db.query(League).filter_by(slug="nfl").first()
    if not league:
        league = League(sport_id=sport.id, name="NFL", slug="nfl")
        db.add(league)
        db.flush()

    team_names = {"1": "Test Team", "2": "Test Opponent", "3": "Test Rival", "4": "Test Challenger"}
    teams = {}
    for ext_id, name in team_names.items():
        t = db.query(Team).filter_by(league_id=league.id, external_id=ext_id, provider="api_sports_nfl").first()
        if not t:
            t = Team(league_id=league.id, external_id=ext_id, provider="api_sports_nfl", name=name)
            db.add(t)
            db.flush()
        teams[ext_id] = t

    strength = {"1": 90, "2": 75, "3": 60, "4": 45}
    team_ids = list(team_names.keys())
    pairs = [(a, b) for i, a in enumerate(team_ids) for b in team_ids[i+1:]]
    schedule = (pairs * 3)[:16]

    random.seed(7)
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    created = 0
    for i, (a, b) in enumerate(schedule):
        home_id, away_id = (a, b) if i % 2 == 0 else (b, a)
        ext_id = f"seed-g{i+1}"
        if db.query(Game).filter_by(league_id=league.id, external_id=ext_id, provider="api_sports_nfl").first():
            continue
        home_score = max(0, round(strength[home_id] / 4 + 3 + random.gauss(0, 4)))
        away_score = max(0, round(strength[away_id] / 4 + random.gauss(0, 4)))
        db.add(Game(
            league_id=league.id, external_id=ext_id, provider="api_sports_nfl", season="2026",
            game_date=base + timedelta(days=7 * (i // 2)),
            home_team_id=teams[home_id].id, away_team_id=teams[away_id].id,
            status="final", home_score=home_score, away_score=away_score,
        ))
        created += 1

    db.commit()
    return {"teams_seeded": len(teams), "games_created": created}


class AuthRequest(BaseModel):
    email: str
    password: str
    full_name: str = None


class ProfileUpdateRequest(BaseModel):
    full_name: str = None
    phone: str = None
    email: str = None


@app.post("/auth/signup")
def signup_endpoint(body: AuthRequest, db: Session = Depends(get_db)):
    try:
        user, token = sign_up(db, body.email, body.password, full_name=body.full_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"token": token, "email": user.email, "full_name": user.full_name}


@app.post("/auth/login")
def login_endpoint(body: AuthRequest, db: Session = Depends(get_db)):
    try:
        user, token = log_in(db, body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    return {"token": token, "email": user.email, "full_name": user.full_name}


@app.post("/auth/logout")
def logout_endpoint(authorization: str = Header(None), db: Session = Depends(get_db)):
    if authorization:
        log_out(db, authorization)
    return {"status": "logged_out"}


@app.patch("/auth/profile")
def update_profile_endpoint(body: ProfileUpdateRequest, authorization: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(db, authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in or session expired.")

    try:
        updated = update_profile(db, user, full_name=body.full_name, phone=body.phone, email=body.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"email": updated.email, "full_name": updated.full_name, "phone": updated.phone}


@app.post("/auth/deactivate")
def deactivate_endpoint(authorization: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(db, authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in or session expired.")

    deactivate_account(db, user)
    return {"status": "deactivated"}


@app.get("/auth/me")
def me_endpoint(authorization: str = Header(None), db: Session = Depends(get_db)):
    user = get_current_user(db, authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in or session expired.")
    return {"email": user.email, "full_name": user.full_name, "phone": user.phone}
