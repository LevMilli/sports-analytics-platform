"""
Games list pipeline (multipage website, part 1).

Every endpoint built through Milestone 9 answers a question about ONE
game or runs a whole-league computation. The dashboard needs
something neither provides: a list of MANY games at once, each with
just enough info to show in a row.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.db.models.core import Game, Team, League, TeamGameFeatures


def list_games_for_league(db: Session, league_slug: str, status: Optional[str] = None, limit: int = 50) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    query = db.query(Game).filter(Game.league_id == league.id)
    if status:
        query = query.filter(Game.status == status)
    games = query.order_by(Game.game_date.asc()).limit(limit).all()

    results = []
    for game in games:
        home_team = db.query(Team).filter_by(id=game.home_team_id).first()
        away_team = db.query(Team).filter_by(id=game.away_team_id).first()
        home_f = db.query(TeamGameFeatures).filter_by(game_id=game.id, team_id=game.home_team_id).first()

        results.append({
            "game_id": game.id,
            "home_team": home_team.name if home_team else None,
            "away_team": away_team.name if away_team else None,
            "game_date": game.game_date.isoformat() if game.game_date else None,
            "status": game.status,
            "home_score": game.home_score,
            "away_score": game.away_score,
            "elo_win_prob_home": float(home_f.elo_win_prob) if home_f and home_f.elo_win_prob is not None else None,
        })

    return {"games": results, "count": len(results)}
