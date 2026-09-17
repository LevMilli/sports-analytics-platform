"""
Authentication pipeline.

Password hashing uses PBKDF2-HMAC-SHA256 from Python's own hashlib --
no external dependency, no bcrypt/passlib needed. Same algorithm
Django uses by default. Each password gets its own random salt.

Sessions are opaque random tokens, stored in their own table with an
expiry -- not JWTs. That makes logout instantaneous.

Session rows optionally carry the real User-Agent header sent at
login/signup time, so a user can see (and individually revoke) which
real devices/browsers are currently signed in -- no invented location
data, since we have no real geolocation infrastructure to back that.
"""

import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List

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


def _create_session(db: DbSession, user_id: int, user_agent: Optional[str] = None) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_LIFETIME_DAYS)
    trimmed_agent = user_agent[:255] if user_agent else None
    db.add(Session_(user_id=user_id, token=token, user_agent=trimmed_agent, expires_at=expires))
    return token


def sign_up(db: DbSession, email: str, password: str, full_name: Optional[str] = None,
            user_agent: Optional[str] = None) -> Tuple[User, str]:
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
    user = User(email=email, password_hash=password_hash, password_salt=salt, full_name=full_name)
    db.add(user)
    db.flush()

    token = _create_session(db, user.id, user_agent=user_agent)
    db.commit()
    return user, token


def log_in(db: DbSession, email: str, password: str, user_agent: Optional[str] = None) -> Tuple[User, str]:
    email = email.strip().lower()
    user = db.query(User).filter_by(email=email).first()
    if not user or not _verify_password(password, user.password_salt, user.password_hash):
        raise ValueError("Incorrect email or password.")
    if not user.is_active:
        raise ValueError("This account has been deactivated.")

    token = _create_session(db, user.id, user_agent=user_agent)
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
    user = db.query(User).filter_by(id=session.user_id).first()
    if user and not user.is_active:
        return None
    return user


def log_out(db: DbSession, token: str) -> None:
    db.query(Session_).filter_by(token=token).delete()
    db.commit()


def update_profile(db: DbSession, user: User, full_name: Optional[str] = None,
                    phone: Optional[str] = None, email: Optional[str] = None) -> User:
    if email is not None:
        email = email.strip().lower()
        if not email or "@" not in email:
            raise ValueError("A valid email address is required.")
        if email != user.email:
            existing = db.query(User).filter_by(email=email).first()
            if existing:
                raise ValueError("An account with this email already exists.")
            user.email = email

    if full_name is not None:
        user.full_name = full_name.strip() or None
    if phone is not None:
        user.phone = phone.strip() or None

    db.commit()
    return user


def deactivate_account(db: DbSession, user: User) -> None:
    user.is_active = False
    db.query(Session_).filter_by(user_id=user.id).delete()
    db.commit()


def list_sessions(db: DbSession, token: str) -> Tuple[User, List[Session_], int]:
    """
    Returns (user, sessions, current_session_id) for the account that
    owns `token` -- every real active session on file for them,
    ordered newest first, plus which one is the request's own.
    """
    user = get_current_user(db, token)
    if not user:
        raise ValueError("Not logged in or session expired.")

    now = datetime.now(timezone.utc)
    sessions = (
        db.query(Session_)
        .filter_by(user_id=user.id)
        .order_by(Session_.created_at.desc())
        .all()
    )
    active_sessions = [s for s in sessions if s.expires_at.replace(tzinfo=timezone.utc) >= now]

    current = db.query(Session_).filter_by(token=token).first()
    current_id = current.id if current else None

    return user, active_sessions, current_id


def revoke_session(db: DbSession, token: str, session_id: int) -> None:
    """
    Revokes one specific session by id -- but only if it genuinely
    belongs to the account making the request. Without that ownership
    check, a logged-in user could log anyone else out by guessing IDs.
    """
    user = get_current_user(db, token)
    if not user:
        raise ValueError("Not logged in or session expired.")

    session = db.query(Session_).filter_by(id=session_id, user_id=user.id).first()
    if not session:
        raise ValueError("Session not found.")

    db.delete(session)
    db.commit()
