from datetime import UTC, date, datetime

from fastapi import Depends

from app.api.dependencies.auth import require_user
from app.models.user import User
from app.services.timezones import user_today


def get_now() -> datetime:
    """The current moment (UTC, timezone-aware). Tests replace it via dependency_overrides."""
    return datetime.now(UTC)


def get_user_today(user: User = Depends(require_user), now: datetime = Depends(get_now)) -> date:
    """Today in the time zone of the logged-in account."""
    return user_today(user, now)
