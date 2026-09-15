"""
Authentication pipeline.

Password hashing uses PBKDF2-HMAC-SHA256 from Python's own hashlib --
no external dependency, no bcrypt/passlib needed. Same algorithm
Django uses by default. Each password gets its own random salt, so
two users with the same password never produce the same stored hash.

Sessions are opaque random tokens, stored in their own table with an
expiry -- not JWTs. That makes logout instantaneous (delete the row)
rather than "wait for the token to expire," and never requires
managing a signing secret.
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session as DbSession

from app.db.models.core import User, Session_

PBKDF2_ITERATIONS = 600_000
SESSION_LIFETIME_DAYS = 30


def _hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return dk.hex()


def _make_salt() -> str:
    return secrets.token_hex(16)


def _verify_password(password: str, salt: str, expected_hash: str) -> bool:
    actual_hash = _hash_password(password, salt)
    return secrets.compare_digest(actual_hash, expected_hash)


def _create_session(db: DbSession, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_LIFETIME_DAYS)
    db.add(Session_(user_id=user_id, token=token, expires_at=expires))
    return token


def sign_up(db: DbSession, email: str, password: str) -> Tuple[User, str]:
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    existing = db.query(User).filter_by(email=email).first()
    if existing:
        raise ValueError("An account with this email already exists.")

    salt = _make_salt()
    password_hash = _hash_password(password, salt)
    user = User(email=email, password_hash=password_hash, password_salt=salt)
    db.add(user)
    db.flush()

    token = _create_session(db, user.id)
    db.commit()
    return user, token


def log_in(db: DbSession, email: str, password: str) -> Tuple[User, str]:
    email = email.strip().lower()
    user = db.query(User).filter_by(email=email).first()
    if not user or not _verify_password(password, user.password_salt, user.password_hash):
        raise ValueError("Incorrect email or password.")

    token = _create_session(db, user.id)
    db.commit()
    return user, token


def get_current_user(db: DbSession, token: str) -> Optional[User]:
    if not token:
        return None
    session = db.query(Session_).filter_by(token=token).first()
    if not session:
        return None
    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return db.query(User).filter_by(id=session.user_id).first()


def log_out(db: DbSession, token: str) -> None:
    db.query(Session_).filter_by(token=token).delete()
    db.commit()
