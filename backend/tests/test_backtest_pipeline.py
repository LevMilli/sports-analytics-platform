"""
Tests for backtest_pipeline.py.

Reuses the same 3-game scenario as elo/feature tests. Expected
accuracy/Brier/log-loss values were independently hand-calculated in
a fresh standalone script (not by re-running this module's own code)
and confirmed to match live database output within Postgres's
stored-column rounding (see milestone_6_explained.md):
accuracy 0.33333, brier_score 0.30240, log_loss 0.80118.
"""

from datetime import datetime, timezone, timedelta

from app.db.models.core import Sport, League, Team, Game
from app.features.elo_pipeline import compute_elo_for_league
from app.features.backtest_pipeline import run_backtest_for_league


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
    return games


def test_backtest_metrics_match_independently_calculated_values(db_session):
    _seed_three_game_scenario(db_session)
    compute_elo_for_league(db_session, "nfl")
    result = run_backtest_for_league(db_session, "nfl", model_name="elo")

    assert result["games_evaluated"] == 3
    assert abs(result["accuracy"] - (1 / 3)) < 0.001
    assert abs(result["brier_score"] - 0.30240) < 0.001
    assert abs(result["log_loss"] - 0.80118) < 0.001


def test_unknown_model_name_is_rejected(db_session):
    import pytest
    _seed_three_game_scenario(db_session)
    compute_elo_for_league(db_session, "nfl")

    with pytest.raises(ValueError, match="Unknown model_name"):
        run_backtest_for_league(db_session, "nfl", model_name="not-a-real-model")
