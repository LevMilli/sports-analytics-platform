"""
Elo rating pipeline (Milestone 5, part 1).

Unlike the rolling-form features in feature_pipeline.py -- which only
look at ONE team's own history -- Elo ratings are inherently a
two-team, whole-league thing: a single game updates BOTH teams'
ratings at once, so this has to walk every game in the league in true
chronological order (not one team at a time) while keeping a running
{team_id: rating} dict in memory.

For every game (played OR still scheduled), this writes each team's
PRE-GAME Elo rating and the Elo-implied win probability for that game.
That's the actual prediction: for a scheduled game, elo_win_prob is
this model's forecast, computed from both teams' current ratings
before a single new result updates anything further. Only COMPLETED
games (final status, both scores present) actually move the ratings
forward for the next game in the loop.
"""

from typing import Dict
from sqlalchemy.orm import Session

from app.db.models.core import Game, Team, League, TeamGameFeatures, IngestionLog, PredictionSnapshot

STARTING_RATING = 1500.0
K_FACTOR = 20.0
HOME_ADVANTAGE = 65.0


def _log(db: Session, source: str, stage: str, status: str, count: int, message: str = ""):
    db.add(IngestionLog(
        source=source, stage=stage, status=status,
        records_processed=count, message=message,
    ))


def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def _upsert_elo(db: Session, game_id: int, team_id: int, elo_rating: float, elo_win_prob: float):
    row = db.query(TeamGameFeatures).filter_by(game_id=game_id, team_id=team_id).first()
    if row:
        row.elo_rating = elo_rating
        row.elo_win_prob = elo_win_prob
    else:
        db.add(TeamGameFeatures(
            game_id=game_id,
            team_id=team_id,
            is_home=False,
            games_played_prior=0,
            elo_rating=elo_rating,
            elo_win_prob=elo_win_prob,
        ))


def compute_elo_for_league(db: Session, league_slug: str) -> dict:
    league = db.query(League).filter_by(slug=league_slug).first()
    if not league:
        raise ValueError(f"No league found with slug '{league_slug}'")

    games = (
        db.query(Game)
        .filter(Game.league_id == league.id)
        .order_by(Game.game_date.asc())
        .all()
    )

    ratings: Dict[int, float] = {}
    rows_written = 0

    for game in games:
        home_id, away_id = game.home_team_id, game.away_team_id
        home_elo = ratings.get(home_id, STARTING_RATING)
        away_elo = ratings.get(away_id, STARTING_RATING)

        expected_home = _expected_score(home_elo + HOME_ADVANTAGE, away_elo)
        expected_away = 1.0 - expected_home

        _upsert_elo(db, game.id, home_id, home_elo, expected_home)
        _upsert_elo(db, game.id, away_id, away_elo, expected_away)
        db.add(PredictionSnapshot(game_id=game.id, team_id=home_id, model_name="elo", win_probability=expected_home))
        db.add(PredictionSnapshot(game_id=game.id, team_id=away_id, model_name="elo", win_probability=expected_away))
        rows_written += 2

        is_complete = game.status == "final" and game.home_score is not None and game.away_score is not None
        if is_complete:
            if game.home_score > game.away_score:
                actual_home = 1.0
            elif game.away_score > game.home_score:
                actual_home = 0.0
            else:
                actual_home = 0.5
            actual_away = 1.0 - actual_home

            ratings[home_id] = home_elo + K_FACTOR * (actual_home - expected_home)
            ratings[away_id] = away_elo + K_FACTOR * (actual_away - expected_away)

    _log(db, "elo_pipeline", f"compute_{league_slug}", "success", rows_written)
    db.commit()

    return {
        "games_processed": len(games),
        "rows_written": rows_written,
        "final_ratings": {
            team.name: round(ratings[team.id], 1)
            for team in db.query(Team).filter_by(league_id=league.id).all()
            if team.id in ratings
        },
    }
