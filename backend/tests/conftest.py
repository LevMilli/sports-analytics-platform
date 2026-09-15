"""
Shared test fixtures.

We use an in-memory SQLite database for these tests rather than
Postgres. That keeps the ingestion pipeline tests fast and dependency-free
(no Docker needed to run `pytest`), since the pipeline logic being
tested here doesn't rely on any Postgres/Timescale-specific features.
Odds/time-series tests in later milestones will run against a real
Postgres+Timescale test container instead, since hypertable behavior
can't be validated on SQLite.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.db import models  # noqa: F401


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
