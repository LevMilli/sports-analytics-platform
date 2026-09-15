"""
Database engine and session factory.

Why this exists:
FastAPI endpoints and ingestion jobs both need a DB session, but neither
should know how the engine is configured. get_db() is used as a FastAPI
dependency; get_session() is a plain context-manager style helper for
non-request code (like ingestion scripts and tests).
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session():
    """Plain context manager for use outside of FastAPI request handling."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
