"""
Tests for explain_pipeline.py.

Reuses the same 3-game scenario. Expected factors, confidence, and
sample size for game 3 were hand-derived and confirmed to match live
output exactly (see milestone_7_explained.md): 3 factors all favoring
the home team, confidence 40, sample_size "medium".
"""

from datetime import datetime, timezone, timedelta

from app.db.models.core import Sport, League, Team, Game
from app.features.feature_pipeline import compute_features_for_team
from app.features.elo_pipeline import compute_elo_for_league
from app.features.explain_pipeline import explain_game


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

    compute_features_for_team(db_session, team1)
    compute_features_for_team(db_session, team2)
    compute_elo_for_league(db_session, "nfl")

    return team1, team2, games


def test_third_game_explanation_matches_verified_output(db_session):
    team1, team2, games = _seed_three_game_scenario(db_session)
    result = explain_game(db_session, games[2].id)

    assert len(result["factors"]) == 3
    assert all(f["favors"] == "home" for f in result["factors"])
    assert result["confidence"] == 40
    assert result["sample_size"] == "medium"
    assert result["sample_size_games"] == 2


def test_equal_rest_days_produces_no_rest_factor(db_session):
    team1, team2, games = _seed_three_game_scenario(db_session)
    result = explain_game(db_session, games[2].id)

    assert not any("rest" in f["text"].lower() for f in result["factors"])


def test_missing_game_raises_value_error(db_session):
    import pytest
    with pytest.raises(ValueError, match="No game found"):
        explain_game(db_session, 999999)
