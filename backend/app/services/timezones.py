"""Time zone and day end per account: "today" is always the account's own day.

An account without its own time zone uses the server's DEFAULT_TIMEZONE. With a day end after
midnight (day_end_hour), the hours before it still belong to the day before. Check-ins are
calendar days and never move; changing either setting only changes which day is "today".
"""

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, available_timezones

from app.config import get_default_timezone, get_default_timezone_name
from app.models.user import User
from app.services.day_service import today_in


@lru_cache(maxsize=1)
def known_timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def is_known_timezone(name: str) -> bool:
    return name in known_timezones()


def effective_timezone_name(user: User) -> str:
    # A zone that disappeared from the tz database falls back instead of failing every request
    if user.timezone and is_known_timezone(user.timezone):
        return user.timezone
    return get_default_timezone_name()


def user_zone(user: User) -> ZoneInfo:
    if user.timezone and is_known_timezone(user.timezone):
        return ZoneInfo(user.timezone)
    return get_default_timezone()


def user_today(user: User, now: datetime) -> date:
    return today_in(user_zone(user), now, user.day_end_hour or 0)
