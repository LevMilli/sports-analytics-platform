"""
Favorite teams -- lets a signed-in user save teams they care about.
Purely a saved preference (which teams to watch), scoped to the
authenticated user: one person's favorites are never visible to or
editable by another.
"""

from typing import List, Optional
from sqlalchemy.orm import Session as DbSession

from app.db.models.core import FavoriteTeam, Team, League
from app.features.auth_pipeline import get_current_user


def add_favorite(db: DbSession, token: str, team_id: int) -> dict:
    user = get_current_user(db, token)
    if not user:
        raise ValueError("Not logged in or session expired.")

    team = db.query(Team).filter_by(id=team_id).first()
    if not team:
        raise ValueError(f"No team found with id {team_id}")

    existing = db.query(FavoriteTeam).filter_by(user_id=user.id, team_id=team_id).first()
    if existing:
        return {"team_id": team_id, "team_name": team.name, "already_favorited": True}

    db.add(FavoriteTeam(user_id=user.id, team_id=team_id))
    db.commit()
    return {"team_id": team_id, "team_name": team.name, "already_favorited": False}


def remove_favorite(db: DbSession, token: str, team_id: int) -> None:
    user = get_current_user(db, token)
    if not user:
        raise ValueError("Not logged in or session expired.")

    db.query(FavoriteTeam).filter_by(user_id=user.id, team_id=team_id).delete()
    db.commit()


def list_favorites(db: DbSession, token: str) -> List[dict]:
    user = get_current_user(db, token)
    if not user:
        raise ValueError("Not logged in or session expired.")

    rows = (
        db.query(FavoriteTeam, Team, League)
        .join(Team, Team.id == FavoriteTeam.team_id)
        .join(League, League.id == Team.league_id)
        .filter(FavoriteTeam.user_id == user.id)
        .order_by(FavoriteTeam.created_at.desc())
        .all()
    )
    return [
        {"team_id": t.id, "team_name": t.name, "league": lg.slug}
        for _, t, lg in rows
    ]


def search_teams(db: DbSession, query: str, league_slug: Optional[str] = None, limit: int = 10) -> List[dict]:
    q = db.query(Team, League).join(League, League.id == Team.league_id)
    if league_slug:
        q = q.filter(League.slug == league_slug)
    q = q.filter(Team.name.ilike(f"%{query}%"))
    rows = q.limit(limit).all()
    return [{"team_id": t.id, "team_name": t.name, "league": lg.slug} for t, lg in rows]
