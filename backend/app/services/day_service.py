"""Pure date logic: state per habit and day, weekly quota.

"Today" always comes from the configured time zone (DEFAULT_TIMEZONE), never from
the container's UTC clock.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

ALL_WEEKDAYS = 0b1111111

DayState = Literal["not_planned", "open", "done", "extra_done", "future"]


class ScheduleLike(Protocol):
    valid_from: date
    weekdays: int


@dataclass(frozen=True)
class DayInfo:
    date: date
    planned: bool
    done: bool
    state: DayState


@dataclass(frozen=True)
class Quota:
    done: int
    due: int


def today_in(zone: ZoneInfo, now: datetime | None = None) -> date:
    moment = now if now is not None else datetime.now(zone)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment.astimezone(zone).date()


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekday_bit(day: date) -> int:
    return 1 << day.weekday()


def weekdays_for(schedules: Sequence[ScheduleLike], day: date) -> int:
    """Weekdays of the plan in effect on that day (largest valid_from <= day)."""
    current = 0
    for schedule in sorted(schedules, key=lambda s: s.valid_from):
        if schedule.valid_from <= day:
            current = schedule.weekdays
        else:
            break
    return current


def is_planned(schedules: Sequence[ScheduleLike], day: date) -> bool:
    return bool(weekdays_for(schedules, day) & weekday_bit(day))


def day_state(planned: bool, done: bool, day: date, today: date) -> DayState:
    if day > today:
        return "future"
    if done:
        return "done" if planned else "extra_done"
    return "open" if planned else "not_planned"


def date_range(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def build_days(
    schedules: Sequence[ScheduleLike],
    done_dates: set[date],
    start: date,
    end: date,
    today: date,
) -> list[DayInfo]:
    result = []
    for day in date_range(start, end):
        planned = is_planned(schedules, day)
        done = day in done_dates and day <= today
        result.append(DayInfo(day, planned, done, day_state(planned, done, day, today)))
    return result


def quota(days: Iterable[DayInfo], today: date) -> Quota:
    """ "4 of 5": done planned days / due planned days.

    Due are planned days before today; today only counts once it is done.
    Future and unplanned days never count against the quota, and extra check-ins
    on unplanned days do not count for it.
    """
    done = due = 0
    for info in days:
        if not info.planned or info.date > today:
            continue
        if info.date < today or info.done:
            due += 1
        if info.done:
            done += 1
    return Quota(done=done, due=due)
