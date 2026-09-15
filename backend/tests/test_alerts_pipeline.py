"""
Tests for alerts_pipeline.py.

Reuses the "brand-new team with zero game history" scenario seeded
live tonight, which produced a confidence of exactly 0 and a
low_confidence alert (see milestone_9_explained.md).
"""

from datetime import datetime, timezone, timedelta

from app.db.models.core import Sport, League, Team, Game, Alert
from app.features.feature_pipeline import compute_features_for_league
from app.features.elo_pipeline import compute_elo_for_league
from app.features.alerts_pipeline import generate_alerts_for_league


def _seed_established_team_and_rookie(db_session):
    sport = Sport(name="Football", slug="football")
    db_session.add(sport)
    db_session.flush()

    league = League(sport_id=sport.id, name="NFL", slug="nfl")
    db_session.add(league)
    db_session.flush()

    established = Team(league_id=league.id, external_id="1", provider="test", name="Established Team")
    rookie = Team(league_id=league.id, external_id="2", provider="test", name="Rookie Team")
    db_session.add_all([established, rookie])
    db_session.flush()

    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    filler = Team(league_id=league.id, external_id="3", provider="test", name="Filler Opponent")
    db_session.add(filler)
    db_session.flush()

    past_game = Game(
        league_id=league.id, external_id="past1", provider="test", season="2026",
        game_date=base, home_team_id=established.id, away_team_id=filler.id,
        status="final", home_score=20, away_score=10,
    )
    scheduled_game = Game(
        league_id=league.id, external_id="future1", provider="test", season="2026",
        game_date=base + timedelta(days=7),
        home_team_id=established.id, away_team_id=rookie.id, status="scheduled",
    )
    db_session.add_all([past_game, scheduled_game])
    db_session.commit()

    return league, established, rookie, scheduled_game


def test_zero_history_team_triggers_low_confidence_alert(db_session):
    league, established, rookie, scheduled_game = _seed_established_team_and_rookie(db_session)

    compute_features_for_league(db_session, "nfl")
    compute_elo_for_league(db_session, "nfl")
    result = generate_alerts_for_league(db_session, "nfl")

    assert result["games_checked"] == 1
    assert result["alerts_active"] == 1

    alert = db_session.query(Alert).filter_by(game_id=scheduled_game.id, alert_type="low_confidence").first()
    assert alert is not None
    assert "0%" in alert.message


def test_rerunning_alerts_does_not_duplicate(db_session):
    league, established, rookie, scheduled_game = _seed_established_team_and_rookie(db_session)

    compute_features_for_league(db_session, "nfl")
    compute_elo_for_league(db_session, "nfl")
    generate_alerts_for_league(db_session, "nfl")
    generate_alerts_for_league(db_session, "nfl")

    alerts = db_session.query(Alert).filter_by(game_id=scheduled_game.id, alert_type="low_confidence").all()
    assert len(alerts) == 1


def test_completed_games_are_never_checked(db_session):
    league, established, rookie, scheduled_game = _seed_established_team_and_rookie(db_session)
    compute_features_for_league(db_session, "nfl")
    compute_elo_for_league(db_session, "nfl")
    result = generate_alerts_for_league(db_session, "nfl")

    assert result["games_checked"] == 1
