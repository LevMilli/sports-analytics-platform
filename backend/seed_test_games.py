"""One-off script: seeds a second team and 3 completed games between
'Test Team' and 'Test Opponent', so the feature pipeline has real
data to compute rolling averages from."""

from datetime import datetime, timezone, timedelta
from app.db.session import SessionLocal
from app.db.models.core import Sport, League, Team, Game

db = SessionLocal()

sport = db.query(Sport).filter_by(slug="football").first()
league = db.query(League).filter_by(slug="nfl").first()
team1 = db.query(Team).filter_by(league_id=league.id, external_id="1", provider="api_sports_nfl").first()

team2 = db.query(Team).filter_by(league_id=league.id, external_id="2", provider="api_sports_nfl").first()
if not team2:
    team2 = Team(league_id=league.id, external_id="2", provider="api_sports_nfl", name="Test Opponent")
    db.add(team2)
    db.flush()

base = datetime(2026, 9, 1, tzinfo=timezone.utc)

games_data = [
    {"external_id": "g1", "home": team1, "away": team2, "days": 0, "home_score": 24, "away_score": 17},
    {"external_id": "g2", "home": team2, "away": team1, "days": 7, "home_score": 20, "away_score": 27},
    {"external_id": "g3", "home": team1, "away": team2, "days": 14, "home_score": 10, "away_score": 14},
]

for g in games_data:
    existing = db.query(Game).filter_by(league_id=league.id, external_id=g["external_id"], provider="api_sports_nfl").first()
    if not existing:
        db.add(Game(
            league_id=league.id,
            external_id=g["external_id"],
            provider="api_sports_nfl",
            season="2026",
            game_date=base + timedelta(days=g["days"]),
            home_team_id=g["home"].id,
            away_team_id=g["away"].id,
            status="final",
            home_score=g["home_score"],
            away_score=g["away_score"],
        ))

db.commit()
print("Seeded team2 id:", team2.id, "and 3 games")
db.close()
