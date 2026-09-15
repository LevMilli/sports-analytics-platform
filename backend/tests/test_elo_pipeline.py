"""
Tests for elo_pipeline.py.

Reuses the same 3-game scenario, with pre-game Elo ratings and win
probabilities that were hand-calculated, then confirmed to match live
database output exactly (see milestone_5_explained.md):
game1 1500.00/0.5925, game2 1508.15/0.4304 (away team's number, since
game2's home team is team2), game3 1519.54/0.6455.
"""

from datetime import datetime, timezone, timedelta

from app.db.models.core import Sport, League, Team, Game, TeamGameFeatures
from app.features.elo_pipeline import compute_elo_for_league


def _seed_three_game_scenario(db_session):
    sport = Sport(name="Football", slug="football")
    db_session.add(sport)
    db_session.flush()

    league = League(sport_id=sport.id, name="NFL", slug="nfl")
    db_session.add(league)
    db_session.flush()

    team1 = Team(league_id=league.id, external_id="1", provider="test", name="Team One")
    team2 = Team(league_id=league.id, external_id="2", provider="test", name="Team Two")
    db_session.add_all([team1, team2])
    db_session.flush()

    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    games = [
        Game(league_id=league.id, external_id="g1", provider="test", season="2026",
             game_date=base, home_team_id=team1.id, away_team_id=team2.id,
             status="final", home_score=24, away_score=17),
        Game(league_id=league.id, external_id="g2", provider="test", season="2026",
             game_date=base + timedelta(days=7), home_team_id=team2.id, away_team_id=team1.id,
             status="final", home_score=20, away_score=27),
        Game(league_id=league.id, external_id="g3", provider="test", season="2026",
             game_date=base + timedelta(days=14), home_team_id=team1.id, away_team_id=team2.id,
             status="final", home_score=10, away_score=14),
    ]
    db_session.add_all(games)
    db_session.commit()
    return league, team1, team2, games


def test_elo_ratings_and_probabilities_match_verified_values(db_session):
    league, team1, team2, games = _seed_three_game_scenario(db_session)
    result = compute_elo_for_league(db_session, "nfl")

    assert result["games_processed"] == 3

    game1_home = db_session.query(TeamGameFeatures).filter_by(game_id=games[0].id, team_id=team1.id).first()
    assert abs(float(game1_home.elo_rating) - 1500.00) < 0.01
    assert abs(float(game1_home.elo_win_prob) - 0.5925) < 0.001

    game2_home = db_session.query(TeamGameFeatures).filter_by(game_id=games[1].id, team_id=team2.id).first()
    assert abs(float(game2_home.elo_rating) - 1491.849) < 0.01

    game3_home = db_session.query(TeamGameFeatures).filter_by(game_id=games[2].id, team_id=team1.id).first()
    assert abs(float(game3_home.elo_rating) - 1519.543) < 0.01
    assert abs(float(game3_home.elo_win_prob) - 0.6455) < 0.001


def test_home_and_away_probabilities_sum_to_one(db_session):
    league, team1, team2, games = _seed_three_game_scenario(db_session)
    compute_elo_for_league(db_session, "nfl")

    for game in games:
        home_f = db_session.query(TeamGameFeatures).filter_by(game_id=game.id, team_id=game.home_team_id).first()
        away_f = db_session.query(TeamGameFeatures).filter_by(game_id=game.id, team_id=game.away_team_id).first()
        total = float(home_f.elo_win_prob) + float(away_f.elo_win_prob)
        assert abs(total - 1.0) < 1e-6
