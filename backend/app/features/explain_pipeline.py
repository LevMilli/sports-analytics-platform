"""
Explainability pipeline (Milestone 7).

Turns a game's Elo prediction and rolling-form features into
plain-language reasons, plus a confidence score based on how much
data each team had on file. No new table -- this reads
team_game_features (already computed by Milestones 4-5) and assembles
a response on the fly.
"""

from typing import Optional
from sqlalchemy.orm import Session

from app.db.models.core import Game, Team, TeamGameFeatures

ROLLING_WINDOW = 5


def _sample_size_label(games: int) -> str:
    if games <= 1:
        return "low"
    elif games <= 3:
        return "medium"
    return "high"


def _factor(text: str, favors: str) -> dict:
    return {"text": text, "favors": favors}


def _build_factors(home_team: Team, away_team: Team,
                    home_f: TeamGameFeatures, away_f: TeamGameFeatures) -> list:
    factors = []

    if home_f.rolling_win_pct is not None and away_f.rolling_win_pct is not None:
        hp, ap = float(home_f.rolling_win_pct), float(away_f.rolling_win_pct)
        if abs(hp - ap) >= 0.001:
            favors = "home" if hp > ap else "away"
            leader, laggard = (home_team, away_team) if hp > ap else (away_team, home_team)
            lead_pct, lag_pct = (hp, ap) if hp > ap else (ap, hp)
            factors.append(_factor(
                f"{leader.name}'s win rate over its recent games ({lead_pct:.0%}) is higher than "
                f"{laggard.name}'s ({lag_pct:.0%}).",
                favors,
            ))

    if (home_f.rolling_points_for_avg is not None and home_f.rolling_points_against_avg is not None
            and away_f.rolling_points_for_avg is not None and away_f.rolling_points_against_avg is not None):
        home_diff = float(home_f.rolling_points_for_avg) - float(home_f.rolling_points_against_avg)
        away_diff = float(away_f.rolling_points_for_avg) - float(away_f.rolling_points_against_avg)
        if abs(home_diff - away_diff) >= 0.5:
            favors = "home" if home_diff > away_diff else "away"
            leader = home_team if home_diff > away_diff else away_team
            lead_diff = home_diff if home_diff > away_diff else away_diff
            factors.append(_factor(
                f"{leader.name} has outscored opponents by {lead_diff:+.1f} points per game recently.",
                favors,
            ))

    if home_f.rest_days is not None and away_f.rest_days is not None:
        if abs(home_f.rest_days - away_f.rest_days) >= 1:
            favors = "home" if home_f.rest_days > away_f.rest_days else "away"
            leader = home_team if home_f.rest_days > away_f.rest_days else away_team
            rest_val = max(home_f.rest_days, away_f.rest_days)
            factors.append(_factor(
                f"{leader.name} enters this game with more rest ({rest_val} days).",
                favors,
            ))

    if home_f.elo_rating is not None and away_f.elo_rating is not None:
        gap = float(home_f.elo_rating) - float(away_f.elo_rating)
        if abs(gap) >= 10:
            favors = "home" if gap > 0 else "away"
            leader = home_team if gap > 0 else away_team
            factors.append(_factor(
                f"{leader.name} carries the higher overall rating entering this game "
                f"(by {abs(gap):.0f} Elo points).",
                favors,
            ))

    return factors


def explain_game(db: Session, game_id: int) -> dict:
    game = db.query(Game).filter_by(id=game_id).first()
    if not game:
        raise ValueError(f"No game found with id {game_id}")

    home_team = db.query(Team).filter_by(id=game.home_team_id).first()
    away_team = db.query(Team).filter_by(id=game.away_team_id).first()

    home_f = db.query(TeamGameFeatures).filter_by(game_id=game_id, team_id=game.home_team_id).first()
    away_f = db.query(TeamGameFeatures).filter_by(game_id=game_id, team_id=game.away_team_id).first()

    if not home_f or not away_f:
        raise ValueError(
            f"No features computed for game {game_id} yet -- "
            f"run /features/nfl/compute and /features/nfl/elo/compute first."
        )

    home_prob = float(home_f.elo_win_prob) if home_f.elo_win_prob is not None else None
    away_prob = float(away_f.elo_win_prob) if away_f.elo_win_prob is not None else None

    factors = _build_factors(home_team, away_team, home_f, away_f)

    home_games = home_f.games_played_prior or 0
    away_games = away_f.games_played_prior or 0
    sample_games = min(home_games, away_games)
    confidence = round(100 * min(sample_games / ROLLING_WINDOW, 1.0))

    return {
        "game_id": game_id,
        "home_team": home_team.name,
        "away_team": away_team.name,
        "model_win_probability": {
            "home": round(home_prob, 4) if home_prob is not None else None,
            "away": round(away_prob, 4) if away_prob is not None else None,
        },
        "factors": factors,
        "confidence": confidence,
        "sample_size": _sample_size_label(sample_games),
        "sample_size_games": sample_games,
    }
