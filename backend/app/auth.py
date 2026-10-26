"""Authentication: password hashing, server-side sessions, current-user dependency (FR1)."""
import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, User

SESSION_TTL = timedelta(hours=12)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD, MAX_PASSWORD = 8, 128

# scrypt parameters (memory-hard; stdlib, no extra dependency)
_N, _R, _P = 2**14, 8, 1


def utcnow() -> datetime:
    """Naive UTC, matching how SQLite hands datetimes back."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(digest_hex) // 2,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# Verified against when the email is unknown, so login time doesn't reveal
# whether an account exists.
_DUMMY_HASH = hash_password("not-a-real-password")


def validate_credentials(email: str, password: str) -> str:
    """Return the normalised email or raise 422."""
    email = email.strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid email address")
    if not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise HTTPException(
            status_code=422,
            detail=f"Password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters",
        )
    return email


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + SESSION_TTL,
        )
    )
    db.commit()
    return token


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if user is None:
        verify_password(password, _DUMMY_HASH)  # equalise timing
        return None
    return user if verify_password(password, user.password_hash) else None


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: resolve the logged-in user or raise 401."""
    unauthorised = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = _bearer_token(authorization)
    if token is None:
        raise unauthorised
    session = db.get(AuthSession, _hash_token(token))
    if session is None:
        raise unauthorised
    if session.expires_at < utcnow():
        db.delete(session)
        db.commit()
        raise unauthorised
    user = db.get(User, session.user_id)
    if user is None:
        raise unauthorised
    return user


def revoke_token(db: Session, authorization: str | None) -> None:
    token = _bearer_token(authorization)
    if token:
        session = db.get(AuthSession, _hash_token(token))
        if session:
            db.delete(session)
            db.commit()
