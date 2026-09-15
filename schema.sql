-- =====================================================================
-- SPORTS DATA ANALYSIS & DECISION-SUPPORT PLATFORM — MVP SCHEMA
-- PostgreSQL 15+ with TimescaleDB extension
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------
-- REFERENCE DATA
-- ---------------------------------------------------------------------

CREATE TABLE sports (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,   -- 'basketball', 'football', etc.
    slug            VARCHAR(50) UNIQUE NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE leagues (
    id              SERIAL PRIMARY KEY,
    sport_id        INTEGER NOT NULL REFERENCES sports(id),
    name            VARCHAR(100) NOT NULL,          -- 'NBA'
    slug            VARCHAR(100) UNIQUE NOT NULL,
    country         VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE teams (
    id              SERIAL PRIMARY KEY,
    league_id       INTEGER NOT NULL REFERENCES leagues(id),
    external_id     VARCHAR(100),                   -- id from source provider
    provider        VARCHAR(50),                     -- which API this id belongs to
    name            VARCHAR(150) NOT NULL,
    abbreviation    VARCHAR(10),
    city            VARCHAR(100),
    venue_name      VARCHAR(150),
    venue_lat       DOUBLE PRECISION,
    venue_lon       DOUBLE PRECISION,
    timezone        VARCHAR(50),
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (league_id, external_id, provider)
);

CREATE TABLE players (
    id              SERIAL PRIMARY KEY,
    team_id         INTEGER REFERENCES teams(id),
    external_id     VARCHAR(100),
    provider        VARCHAR(50),
    full_name       VARCHAR(150) NOT NULL,
    position        VARCHAR(20),
    birth_date      DATE,
    height_cm       INTEGER,
    weight_kg       INTEGER,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (external_id, provider)
);

-- ---------------------------------------------------------------------
-- GAMES
-- ---------------------------------------------------------------------

CREATE TABLE games (
    id                  SERIAL PRIMARY KEY,
    league_id           INTEGER NOT NULL REFERENCES leagues(id),
    external_id         VARCHAR(100),
    provider            VARCHAR(50),
    season              VARCHAR(20),
    game_date           TIMESTAMPTZ NOT NULL,
    home_team_id        INTEGER NOT NULL REFERENCES teams(id),
    away_team_id        INTEGER NOT NULL REFERENCES teams(id),
    venue_name          VARCHAR(150),
    status              VARCHAR(30) NOT NULL DEFAULT 'scheduled', -- scheduled/live/final/postponed
    home_score           INTEGER,
    away_score           INTEGER,
    period_scores_json  JSONB,                       -- [{period:1, home:25, away:20}, ...]
    overtime            BOOLEAN DEFAULT FALSE,
    neutral_site        BOOLEAN DEFAULT FALSE,
    weather_json        JSONB,                        -- temp, wind, precip, etc. (outdoor sports)
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (league_id, external_id, provider)
);

CREATE INDEX idx_games_date ON games (game_date);
CREATE INDEX idx_games_teams ON games (home_team_id, away_team_id);

-- ---------------------------------------------------------------------
-- STATISTICS (wide JSONB for sport-specific flexibility + key indexed cols)
-- ---------------------------------------------------------------------

CREATE TABLE team_game_stats (
    id              SERIAL PRIMARY KEY,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    team_id         INTEGER NOT NULL REFERENCES teams(id),
    is_home         BOOLEAN NOT NULL,
    stats_json      JSONB NOT NULL,     -- sport-specific: pace, off_rtg, def_rtg, rebounds, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, team_id)
);

CREATE TABLE player_game_stats (
    id              SERIAL PRIMARY KEY,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    player_id       INTEGER NOT NULL REFERENCES players(id),
    team_id         INTEGER NOT NULL REFERENCES teams(id),
    started         BOOLEAN DEFAULT FALSE,
    minutes_played  NUMERIC(5,2),
    stats_json      JSONB NOT NULL,     -- points, rebounds, assists, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (game_id, player_id)
);

-- ---------------------------------------------------------------------
-- INJURIES / AVAILABILITY
-- ---------------------------------------------------------------------

CREATE TABLE injury_reports (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER NOT NULL REFERENCES players(id),
    team_id         INTEGER NOT NULL REFERENCES teams(id),
    report_date     TIMESTAMPTZ NOT NULL DEFAULT now(),
    status          VARCHAR(30) NOT NULL,  -- out/doubtful/questionable/probable/available
    description     TEXT,
    source          VARCHAR(100),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_injury_player_date ON injury_reports (player_id, report_date DESC);

-- ---------------------------------------------------------------------
-- ODDS (time-series hypertable)
-- ---------------------------------------------------------------------

CREATE TABLE odds_snapshots (
    id              BIGSERIAL,
    game_id         INTEGER NOT NULL REFERENCES games(id),
    sportsbook      VARCHAR(80) NOT NULL,
    market          VARCHAR(40) NOT NULL,   -- moneyline/spread/total/player_prop
    selection       VARCHAR(150) NOT NULL,  -- 'Team A', 'Over 220.5', 'Player X Over 20.5 pts'
    line_value      NUMERIC(8,2),           -- spread/total number, null for moneyline
    odds_american   INTEGER,
    odds_decimal    NUMERIC(8,3),
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_opening      BOOLEAN DEFAULT FALSE,
    is_closing      BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id, captured_at)
);

SELECT create_hypertable('odds_snapshots', 'captured_at', if_not_exists => TRUE);
CREATE INDEX idx_odds_game_market ON odds_snapshots (game_id, market, captured_at DESC);

-- ---------------------------------------------------------------------
-- MODELS & PREDICTIONS
-- ---------------------------------------------------------------------

CREATE TABLE model_versions (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(100) NOT NULL,     -- 'elo_v1', 'logreg_baseline'
    version             VARCHAR(30) NOT NULL,
    sport_id            INTEGER NOT NULL REFERENCES sports(id),
    model_type          VARCHAR(50) NOT NULL,       -- 'elo','logistic_regression','poisson', etc.
    features_json       JSONB,                       -- list/spec of features used
    hyperparams_json    JSONB,
    training_data_range JSONB,                       -- {start, end}
    metrics_json        JSONB,                       -- accuracy, brier, log_loss, calibration
    trained_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (name, version)
);

CREATE TABLE predictions (
    id                      BIGSERIAL PRIMARY KEY,
    game_id                 INTEGER NOT NULL REFERENCES games(id),
    model_version_id        INTEGER NOT NULL REFERENCES model_versions(id),
    market                  VARCHAR(40) NOT NULL,
    selection               VARCHAR(150) NOT NULL,
    model_probability       NUMERIC(6,4) NOT NULL,
    market_probability      NUMERIC(6,4),
    probability_difference  NUMERIC(6,4),
    model_confidence        NUMERIC(5,2),      -- 0-100
    data_quality_score      NUMERIC(5,2),      -- 0-100
    sample_size_label       VARCHAR(20),        -- low/medium/high
    explanation_json        JSONB,              -- top factors, positive/negative, risks
    predicted_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- outcome fields populated after the game for backtesting/scoring
    actual_outcome          BOOLEAN,
    resolved_at             TIMESTAMPTZ
);

CREATE INDEX idx_predictions_game ON predictions (game_id);
CREATE INDEX idx_predictions_model ON predictions (model_version_id);

-- ---------------------------------------------------------------------
-- BACKTEST RUNS
-- ---------------------------------------------------------------------

CREATE TABLE backtest_runs (
    id                  SERIAL PRIMARY KEY,
    model_version_id    INTEGER NOT NULL REFERENCES model_versions(id),
    date_range_start    DATE NOT NULL,
    date_range_end      DATE NOT NULL,
    n_predictions       INTEGER,
    accuracy            NUMERIC(6,4),
    brier_score         NUMERIC(6,4),
    log_loss            NUMERIC(6,4),
    win_rate            NUMERIC(6,4),
    avg_closing_line_value NUMERIC(6,4),
    max_drawdown        NUMERIC(8,4),
    results_json        JSONB,
    run_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- USERS & ALERTS
-- ---------------------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(30) NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id              SERIAL PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id),
    alert_type      VARCHAR(50) NOT NULL,   -- prob_change/injury/line_move/model_agreement
    config_json     JSONB NOT NULL,          -- thresholds, filters
    channel         VARCHAR(20) NOT NULL DEFAULT 'dashboard', -- dashboard/email/push/sms
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- DATA QUALITY / INGESTION LOGGING
-- ---------------------------------------------------------------------

CREATE TABLE ingestion_logs (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(100) NOT NULL,
    stage           VARCHAR(50) NOT NULL,   -- fetch/validate/normalize/dedupe/store
    status          VARCHAR(20) NOT NULL,    -- success/warning/error
    records_processed INTEGER,
    message         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
