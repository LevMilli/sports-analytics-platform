"""
Feature computation pipeline (Milestone 4). Makes NO network calls --
only reads games already in the database and computes derived
features from them: rest days, and rolling-form (win %, points for/
against) over the last N completed games.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.db.models.core import Game, Team, League, TeamGameFeatures, IngestionLog

ROLLING_WINDOW = 5


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _team_result(game: Game, team_id: int) -> Optional[dict]:
    if game.status != "final":
        return None
    if game.home_score is None or game.away_score is None:
        return None

    if team_id == game.home_team_id:
        points_for, points_against = game.home_score, game.away_score
    elif team_id == game.away_team_id:
        points_for, points_against = game.away_score, game.home_score
    else:
        return None

    return {
        "points_for": points_for,
        "points_against": points_against,
        "win": points_for > points_against,
    }


def compute_features_for_team(db: Session, team: Team) -> int:
    games = (
        db.query(Game)
        .filter((Game.home_team_id == team.id) | (Game.away_team_id == team.id))
        .order_by(Game.game_date.asc())
        .all()
    )

    completed_results = []
    previous_game_date = None
    rows_written = 0

    for game in games:
        is_home = team.id == game.home_team_id

        rest_days = None
        if previous_game_date is not None:
            rest_days = (game.game_date - previous_game_date).days

        window = completed_results[-ROLLING_WINDOW:]
        games_played_prior = len(window)
        if games_played_prior > 0:
            rolling_win_pct = sum(1 for r in window if r["win"]) / games_played_prior
            rolling_points_for_avg = sum(r["points_for"] for r in window) / games_played_prior
            rolling_points_against_avg = sum(r["points_against"] for r in window) / games_played_prior
        else:
            rolling_win_pct = None
            rolling_points_for_avg = None
            rolling_points_against_avg = None

        existing = (
            db.query(TeamGameFeatures)
            .filter_by(game_id=game.id, team_id=team.id)
            .first()
        )
        if existing:
            existing.is_home = is_home
            existing.rest_days = rest_days
            existing.games_played_prior = games_played_prior
            existing.rolling_win_pct = rolling_win_pct
            existing.rolling_points_for_avg = rolling_points_for_avg
            existing.rolling_points_against_avg = rolling_points_against_avg
        else:
            db.add(TeamGameFeatures(
                game_id=game.id,
                team_id=team.id,
                is_home=is_home,
                rest_days=rest_days,
                games_played_prior=games_played_prior,
                rolling_win_pct=rolling_win_pct,
                rolling_points_for_avg=rolling_points_for_avg,
                rolling_points_against_avg=rolling_points_against_avg,
            ))
        rows_written += 1

        result = _team_result(game, team.id)
        if result is not None:
            completed_results.append(result)
        previous_game_date = game.game_date

    return rows_written


def compute_features_for_league(db: Session, league_slug: str) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    teams = db.query(Team).filter_by(league_id=league.id).all()
    results = {}
    total_rows = 0

    for team in teams:
        rows = compute_features_for_team(db, team)
        results[team.name] = {"games_processed": rows}
        total_rows += rows

    _log(db, "feature_pipeline", f"compute_{league_slug}", "success", total_rows)
    db.commit()

    return {"teams_processed": len(teams), "rows_written": total_rows, "results": results}
