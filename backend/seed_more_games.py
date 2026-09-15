"""One-off script: adds 2 more fake teams and a 16-game round-robin
schedule so there's enough completed game history to actually train
the logistic regression model (needs 10+ usable games)."""

import random
from datetime import datetime, timezone, timedelta
from app.db.session import SessionLocal
from app.db.models.core import League, Team, Game

random.seed(7)

db = SessionLocal()
league = db.query(League).filter_by(slug="nfl").first()

team1 = db.query(Team).filter_by(league_id=league.id, external_id="1", provider="api_sports_nfl").first()
team2 = db.query(Team).filter_by(league_id=league.id, external_id="2", provider="api_sports_nfl").first()

team3 = db.query(Team).filter_by(league_id=league.id, external_id="3", provider="api_sports_nfl").first()
if not team3:
    team3 = Team(league_id=league.id, external_id="3", provider="api_sports_nfl", name="Test Rival")
    db.add(team3)
    db.flush()

team4 = db.query(Team).filter_by(league_id=league.id, external_id="4", provider="api_sports_nfl").first()
if not team4:
    team4 = Team(league_id=league.id, external_id="4", provider="api_sports_nfl", name="Test Challenger")
    db.add(team4)
    db.flush()

strength = {team1.id: 90, team2.id: 75, team3.id: 60, team4.id: 45}
team_ids = [team1.id, team2.id, team3.id, team4.id]
pairs = [(a, b) for i, a in enumerate(team_ids) for b in team_ids[i+1:]]
schedule = (pairs * 3)[:16]

base = datetime(2026, 10, 1, tzinfo=timezone.utc)
created = 0

for i, (a, b) in enumerate(schedule):
    home_id, away_id = (a, b) if i % 2 == 0 else (b, a)
    ext_id = f"extra-g{i+1}"
    existing = db.query(Game).filter_by(league_id=league.id, external_id=ext_id, provider="api_sports_nfl").first()
    if existing:
        continue

    home_strength = strength[home_id] + 3  # small home-field bump
    away_strength = strength[away_id]
    home_score = max(0, round(home_strength / 4 + random.gauss(0, 4)))
    away_score = max(0, round(away_strength / 4 + random.gauss(0, 4)))

    db.add(Game(
        league_id=league.id,
        external_id=ext_id,
        provider="api_sports_nfl",
        season="2026",
        game_date=base + timedelta(days=7 * (i // 2)),
        home_team_id=home_id,
        away_team_id=away_id,
        status="final",
        home_score=home_score,
        away_score=away_score,
    ))
    created += 1

db.commit()
print(f"Created {created} new games. team3={team3.id} team4={team4.id}")
db.close()
