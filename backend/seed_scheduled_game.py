"""One-off script: adds a brand-new team (zero game history) and one
scheduled (not yet played) game against an established team, so the
alerts pipeline has something real to check -- a team with zero prior
games should reliably trigger a low_confidence alert."""

from datetime import datetime, timezone, timedelta
from app.db.session import SessionLocal
from app.db.models.core import League, Team, Game

db = SessionLocal()
league = db.query(League).filter_by(slug="nfl").first()

team1 = db.query(Team).filter_by(league_id=league.id, external_id="1", provider="api_sports_nfl").first()

team5 = db.query(Team).filter_by(league_id=league.id, external_id="5", provider="api_sports_nfl").first()
if not team5:
    team5 = Team(league_id=league.id, external_id="5", provider="api_sports_nfl", name="Test Rookie")
    db.add(team5)
    db.flush()

existing = db.query(Game).filter_by(league_id=league.id, external_id="extra-scheduled-1", provider="api_sports_nfl").first()
if not existing:
    db.add(Game(
        league_id=league.id,
        external_id="extra-scheduled-1",
        provider="api_sports_nfl",
        season="2026",
        game_date=datetime.now(timezone.utc) + timedelta(days=7),
        home_team_id=team1.id,
        away_team_id=team5.id,
        status="scheduled",
    ))

db.commit()
print("Seeded team5 id:", team5.id, "and one scheduled game vs Test Team")
db.close()
