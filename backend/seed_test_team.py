from app.db.session import SessionLocal
from app.db.models.core import Sport, League, Team

db = SessionLocal()

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

team = db.query(Team).filter_by(league_id=league.id, external_id="1", provider="api_sports_nfl").first()
if not team:
    team = Team(league_id=league.id, external_id="1", provider="api_sports_nfl", name="Test Team")
    db.add(team)

db.commit()
print("Seeded:", sport.id, league.id, team.id)
db.close()
