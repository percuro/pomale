"""First-run setup: while no account exists, a one-time token printed to the log
allows creating the first account in the browser. This prevents a stranger from
claiming a freshly started public instance before its operator does."""

import hmac
import secrets
from threading import Lock

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User

_lock = Lock()
_token: str | None = None


def needs_setup(db: Session) -> bool:
    return (db.scalar(select(func.count()).select_from(User)) or 0) == 0


def issue_token() -> str:
    """Create a new token (a restart without accounts issues a fresh one)."""
    global _token
    with _lock:
        _token = secrets.token_urlsafe(24)
        return _token


def token_matches(candidate: str) -> bool:
    with _lock:
        current = _token
    return current is not None and hmac.compare_digest(current.encode(), candidate.encode())


def clear_token() -> None:
    global _token
    with _lock:
        _token = None


def setup_lock() -> Lock:
    return _lock
