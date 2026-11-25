"""Pure date logic: state per habit and day, quota, weekly progress.

"Today" always comes from the account's time zone, never from the container's UTC clock.

Two stages:
1. `raw_days` turns plans, pauses and check-ins into one `RawDay` per day, in whole weeks
   (Monday to Sunday). A raw day carries everything the second stage needs.
2. `evaluate` derives states, the quota and the weekly progress from raw days only.

The API sends the raw fields with every day (DayRead), so the web app runs the same
`evaluate` on top of its unconfirmed offline changes (frontend/src/lib/evaluate.ts).
Both implementations are checked against tests/fixtures/quota_cases.json.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

ALL_WEEKDAYS = 0b1111111

GoalType = Literal["days", "weekly_count", "quantity"]
DayState = Literal["not_planned", "open", "done", "extra_done", "future", "paused", "partial"]


class ScheduleLike(Protocol):
    valid_from: date
    weekdays: int
    goal_type: str
    target: int | None


class PauseLike(Protocol):
    start_on: date
    end_on: date


@dataclass(frozen=True)
class Plan:
    weekdays: int = 0
    goal_type: str = "days"
    target: int | None = None


NO_PLAN = Plan()


@dataclass(frozen=True)
class Entry:
    """A stored check-in: `done` for days and weekly goals, `value` for quantity goals."""

    done: bool
    value: int | None = None


@dataclass(frozen=True)
class RawDay:
    date: date
    goal_type: str
    # quantity: target per day; weekly_count: this week's target, reduced for pauses; days: None
    target: int | None
    # due (days, quantity) or counting toward the week (weekly_count); False on paused days
    planned: bool
    # would be planned, but a pause covers the day
    paused: bool
    # checked off (days, weekly_count)
    done: bool
    # quantity: amount so far; 0 otherwise
    value: int = 0


@dataclass(frozen=True)
class DayInfo:
    date: date
    planned: bool
    # days and weekly_count: checked off; quantity: target reached
    done: bool
    state: DayState
    goal_type: str = "days"
    target: int | None = None
    paused: bool = False
    # quantity only
    value: int | None = None


@dataclass(frozen=True)
class Quota:
    done: int
    due: int


@dataclass(frozen=True)
class WeekProgress:
    done: int
    target: int


@dataclass(frozen=True)
class Evaluation:
    days: list[DayInfo]
    quota: Quota
    # the week that contains today, for weekly goals only
    week: WeekProgress | None = None
    # per week overlapping the range: (Monday, quota of that week)
    weeks: list[tuple[date, Quota]] = field(default_factory=list)


def today_in(zone: ZoneInfo, now: datetime | None = None) -> date:
    moment = now if now is not None else datetime.now(zone)
    if moment.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return moment.astimezone(zone).date()


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekday_bit(day: date) -> int:
    return 1 << day.weekday()


def date_range(start: date, end: date) -> Iterable[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def plan_for(schedules: Sequence[ScheduleLike], day: date) -> Plan:
    """The plan in effect on that day (largest valid_from <= day)."""
    current = NO_PLAN
    for schedule in sorted(schedules, key=lambda s: s.valid_from):
        if schedule.valid_from <= day:
            current = Plan(schedule.weekdays, getattr(schedule, "goal_type", None) or "days", schedule.target)
        else:
            break
    return current


def weekdays_for(schedules: Sequence[ScheduleLike], day: date) -> int:
    return plan_for(schedules, day).weekdays


def is_planned(schedules: Sequence[ScheduleLike], day: date) -> bool:
    return bool(weekdays_for(schedules, day) & weekday_bit(day))


def is_paused(pauses: Sequence[PauseLike], day: date) -> bool:
    return any(pause.start_on <= day <= pause.end_on for pause in pauses)


def reduced_target(target: int, active_days: int) -> int:
    """Weekly target for a week with fewer active days (pauses, the first week).

    round(target × active / 7), half up, at least 1 while one active day is left.
    """
    if active_days <= 0:
        return 0
    if active_days >= 7:
        return target
    return max(1, math.floor(target * active_days / 7 + 0.5))


def raw_days(
    schedules: Sequence[ScheduleLike],
    entries: Mapping[date, Entry],
    pauses: Sequence[PauseLike],
    start: date,
    end: date,
    today: date,
) -> list[RawDay]:
    """Raw days for the whole weeks around start..end."""
    result: list[RawDay] = []
    monday = week_start(start)
    while monday <= end:
        sunday = monday + timedelta(days=6)
        days = list(date_range(monday, sunday))
        plans = [plan_for(schedules, day) for day in days]
        active = [bool(plan.weekdays & weekday_bit(day)) for day, plan in zip(days, plans, strict=True)]
        paused = [is_act and is_paused(pauses, day) for day, is_act in zip(days, active, strict=True)]

        week_target: int | None = None
        weekly = [plan for plan in plans if plan.goal_type == "weekly_count"]
        if weekly:
            # The plan in effect at the end of the week; for the running week: today
            reference = plan_for(schedules, today if monday <= today <= sunday else sunday)
            base = reference if reference.goal_type == "weekly_count" else weekly[-1]
            active_weekly = sum(
                1
                for plan, is_active, is_paused_day in zip(plans, active, paused, strict=True)
                if plan.goal_type == "weekly_count" and is_active and not is_paused_day
            )
            week_target = reduced_target(base.target or 1, active_weekly)

        for day, plan, is_active, is_paused_day in zip(days, plans, active, paused, strict=True):
            entry = entries.get(day)
            done = bool(entry and entry.done)
            value = 0
            target = None
            if plan.goal_type == "quantity":
                target = plan.target
                if entry is not None and entry.value is not None:
                    value = entry.value
                elif done:
                    # checked off before the habit became a quantity goal
                    value = target or 1
            elif plan.goal_type == "weekly_count":
                target = week_target
            result.append(
                RawDay(
                    date=day,
                    goal_type=plan.goal_type,
                    target=target,
                    planned=is_active and not is_paused_day,
                    paused=is_paused_day,
                    done=done,
                    value=value,
                )
            )
        monday += timedelta(days=7)
    return result


def _state(day: RawDay, today: date, counted: int, week_checked: int) -> tuple[DayState, bool, bool]:
    """(state, done, counts toward the weekly target)."""
    if day.date > today:
        return "future", False, False
    if day.goal_type == "weekly_count":
        target = day.target or 0
        if day.done:
            if day.planned and counted < target:
                return "done", True, True
            return "extra_done", True, False
        if day.paused:
            return "paused", False, False
        if day.planned and day.date == today and week_checked < target:
            return "open", False, False
        # past days without a check-in are never "missed" for weekly goals
        return "not_planned", False, False
    if day.goal_type == "quantity":
        reached = day.target is not None and day.value >= day.target
        if day.planned:
            if reached:
                return "done", True, False
            return ("partial" if day.value > 0 else "open"), False, False
        if day.value > 0:
            return "extra_done", reached, False
        return ("paused" if day.paused else "not_planned"), False, False
    if day.done:
        return ("done" if day.planned else "extra_done"), True, False
    if day.planned:
        return "open", False, False
    return ("paused" if day.paused else "not_planned"), False, False


def evaluate(days: Sequence[RawDay], today: date, start: date, end: date) -> Evaluation:
    """States for start..end, the quota of that range and the weekly progress.

    `days` must cover whole weeks (as `raw_days` returns them).

    Quota, "4 of 5":
    - days and quantity goals: planned days before today are due; today only once it is done.
      Unplanned, paused and future days never count; extra check-ins do not count.
    - weekly goals: a finished week adds its target to "due" and its check-ins (at most the
      target) to "done". The running week adds only what is already done, to both.
      A range that cuts a week counts the whole week.
    """
    infos: list[DayInfo] = []
    total_done = total_due = 0
    week: WeekProgress | None = None
    weeks: list[tuple[date, Quota]] = []

    by_week: dict[date, list[RawDay]] = {}
    for day in sorted(days, key=lambda d: d.date):
        by_week.setdefault(week_start(day.date), []).append(day)

    for monday, week_days in by_week.items():
        sunday = monday + timedelta(days=6)
        in_range = monday <= end and sunday >= start
        weekly = [d for d in week_days if d.goal_type == "weekly_count"]
        week_target = (weekly[0].target or 0) if weekly else 0
        week_checked = sum(1 for d in weekly if d.planned and d.done and d.date <= today)
        counted = 0
        week_done = week_due = 0
        for day in week_days:
            state, done, counts = _state(day, today, counted, week_checked)
            if counts:
                counted += 1
            if start <= day.date <= end:
                infos.append(
                    DayInfo(
                        date=day.date,
                        planned=day.planned,
                        done=done,
                        state=state,
                        goal_type=day.goal_type,
                        target=day.target,
                        paused=day.paused,
                        value=day.value if day.goal_type == "quantity" else None,
                    )
                )
                if day.goal_type != "weekly_count" and day.planned and day.date <= today:
                    if day.date < today or done:
                        week_due += 1
                    if done:
                        week_done += 1
        if weekly:
            if sunday < today:
                week_due += week_target
                week_done += min(counted, week_target)
            elif monday <= today:
                week_due += counted
                week_done += counted
            if monday <= today <= sunday:
                week = WeekProgress(done=counted, target=week_target)
        if in_range:
            weeks.append((monday, Quota(done=week_done, due=week_due)))
            total_done += week_done
            total_due += week_due

    return Evaluation(days=infos, quota=Quota(done=total_done, due=total_due), week=week, weeks=weeks)


def evaluate_range(
    schedules: Sequence[ScheduleLike],
    entries: Mapping[date, Entry],
    pauses: Sequence[PauseLike],
    start: date,
    end: date,
    today: date,
) -> Evaluation:
    return evaluate(raw_days(schedules, entries, pauses, start, end, today), today, start, end)


def entries_from_done(done_dates: Iterable[date]) -> dict[date, Entry]:
    return {day: Entry(done=True) for day in done_dates}
