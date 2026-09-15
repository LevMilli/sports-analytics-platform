"""
ORM models mirroring the tables needed for Milestones 1-9.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Numeric, ForeignKey,
    UniqueConstraint, Text, JSON
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class Sport(Base):
    __tablename__ = "sports"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    slug = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    leagues = relationship("League", back_populates="sport")


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    sport_id = Column(Integer, ForeignKey("sports.id"), nullable=False)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    country = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)

    sport = relationship("Sport", back_populates="leagues")
    teams = relationship("Team", back_populates="league")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("league_id", "external_id", "provider"),)

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    external_id = Column(String(100))
    provider = Column(String(50))
    name = Column(String(150), nullable=False)
    abbreviation = Column(String(10))
    city = Column(String(100))
    venue_name = Column(String(150))
    venue_lat = Column(String(50))
    venue_lon = Column(String(50))
    timezone = Column(String(50))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    league = relationship("League", back_populates="teams")


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("league_id", "external_id", "provider"),)

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    external_id = Column(String(100))
    provider = Column(String(50))
    season = Column(String(20))
    game_date = Column(DateTime(timezone=True), nullable=False)
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    venue_name = Column(String(150))
    status = Column(String(30), default="scheduled")
    home_score = Column(Integer)
    away_score = Column(Integer)
    overtime = Column(Boolean, default=False)
    neutral_site = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("external_id", "provider"),)

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    external_id = Column(String(100))
    provider = Column(String(50))
    full_name = Column(String(150), nullable=False)
    position = Column(String(20))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TeamGameStats(Base):
    __tablename__ = "team_game_stats"
    __table_args__ = (UniqueConstraint("game_id", "team_id"),)

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    is_home = Column(Boolean, nullable=False)
    stats_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"
    __table_args__ = (UniqueConstraint("game_id", "player_id"),)

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    started = Column(Boolean, default=False)
    minutes_played = Column(Numeric(5, 2))
    stats_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class InjuryReport(Base):
    __tablename__ = "injury_reports"

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    report_date = Column(DateTime(timezone=True), default=utcnow)
    status = Column(String(30), nullable=False)
    description = Column(Text)
    source = Column(String(100))
    created_at = Column(DateTime(timezone=True), default=utcnow)


class TeamGameFeatures(Base):
    __tablename__ = "team_game_features"
    __table_args__ = (UniqueConstraint("game_id", "team_id"),)

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    is_home = Column(Boolean, nullable=False)
    rest_days = Column(Integer)
    games_played_prior = Column(Integer, nullable=False, default=0)
    rolling_win_pct = Column(Numeric(4, 3))
    rolling_points_for_avg = Column(Numeric(6, 2))
    rolling_points_against_avg = Column(Numeric(6, 2))
    elo_rating = Column(Numeric(7, 2))
    elo_win_prob = Column(Numeric(5, 4))
    created_at = Column(DateTime(timezone=True), default=utcnow)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    model_name = Column(String(50), nullable=False)
    games_evaluated = Column(Integer, nullable=False)
    accuracy = Column(Numeric(5, 4))
    brier_score = Column(Numeric(6, 5))
    log_loss = Column(Numeric(7, 5))
    run_at = Column(DateTime(timezone=True), default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("game_id", "team_id", "model_name"),)

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    model_name = Column(String(50), nullable=False)
    win_probability = Column(Numeric(5, 4), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("game_id", "alert_type"),)

    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class IngestionLog(Base):
    __tablename__ = "ingestion_logs"

    id = Column(Integer, primary_key=True)
    source = Column(String(100), nullable=False)
    stage = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    records_processed = Column(Integer)
    message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=utcnow)
