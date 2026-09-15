"""
Tests for feature_pipeline.py.

Uses the exact same 3-game scenario that was hand-verified in a
standalone sandbox script before Milestone 4 was ever wired into the
real project, and later confirmed to match live database output
exactly (rest_days=7, games_played_prior 0/1/2, rolling_win_pct
1.000, rolling_points_for_avg 25.50, rolling_points_against_avg
18.50 -- see milestone_4_explained.md).
"""

from datetime import datetime, timezone, timedelta

from app.db.models.core import Sport, League, Team, Game
from app.features.feature_pipeline import compute_features_for_team


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
    return team1, team2


def test_first_game_has_no_prior_data(db_session):
    team1, _ = _seed_three_game_scenario(db_session)
    compute_features_for_team(db_session, team1)

    from app.db.models.core import TeamGameFeatures
    rows = (
        db_session.query(TeamGameFeatures)
        .filter_by(team_id=team1.id)
        .join(Game, Game.id == TeamGameFeatures.game_id)
        .order_by(Game.game_date.asc())
        .all()
    )
    assert rows[0].rest_days is None
    assert rows[0].games_played_prior == 0
    assert rows[0].rolling_win_pct is None


def test_third_game_rolling_stats_match_verified_values(db_session):
    team1, team2 = _seed_three_game_scenario(db_session)
    compute_features_for_team(db_session, team1)

    from app.db.models.core import TeamGameFeatures
    rows = (
        db_session.query(TeamGameFeatures)
        .filter_by(team_id=team1.id)
        .join(Game, Game.id == TeamGameFeatures.game_id)
        .order_by(Game.game_date.asc())
        .all()
    )
    third = rows[2]
    assert third.rest_days == 7
    assert third.games_played_prior == 2
    assert abs(float(third.rolling_win_pct) - 1.0) < 1e-9
    assert abs(float(third.rolling_points_for_avg) - 25.5) < 1e-9
    assert abs(float(third.rolling_points_against_avg) - 18.5) < 1e-9


def test_unplayed_game_still_gets_features_from_prior_history(db_session):
    team1, team2 = _seed_three_game_scenario(db_session)

    future_game = Game(
        league_id=team1.league_id, external_id="g4", provider="test", season="2026",
        game_date=datetime(2026, 9, 22, tzinfo=timezone.utc),
        home_team_id=team1.id, away_team_id=team2.id, status="scheduled",
    )
    db_session.add(future_game)
    db_session.commit()

    compute_features_for_team(db_session, team1)

    from app.db.models.core import TeamGameFeatures
    row = db_session.query(TeamGameFeatures).filter_by(game_id=future_game.id, team_id=team1.id).first()
    assert row is not None
    assert row.games_played_prior == 3
