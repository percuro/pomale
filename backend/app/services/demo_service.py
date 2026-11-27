"""DEMO_MODE: one shared account with sample data that is reset every full hour.

The data are built as a JSON export and imported, so they go through the same checks as any
import. They depend only on "today": the same day always gives the same demo (screenshots).
Visitors stay signed in across a reset; everything they changed is gone.

The reset deletes everything except the demo account, its sessions and the instance secrets,
so the app refuses to start in demo mode on a database with any other account.
"""

import asyncio
import contextlib
import logging
import random
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import __version__
from app.config import ConfigError
from app.db.database import Base
from app.models.user import ROLE_USER, User, UserSession
from app.repositories.auth_repository import AuthRepository
from app.schemas.export import (
    AccountExport,
    ExportCheckin,
    ExportGroup,
    ExportHabit,
    ExportPause,
    ExportSchedule,
)
from app.services.auth_service import AuthService
from app.services.background import ThreadRuns
from app.services.data_export import import_account
from app.services.timezones import user_today

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "try-pomale-now"
HISTORY_DAYS = 70
# Tables that survive a reset (besides the demo account itself)
KEPT_TABLES = {"users", "user_sessions", "instance_secrets"}

logger = logging.getLogger(__name__)

WEEKDAYS = 0b0011111  # Monday to Friday
EVERY_DAY = 127
MON_WED_FRI = 0b0010101


def _planned(weekdays: int, day: date) -> bool:
    return bool(weekdays & (1 << day.weekday()))


def build_demo(today: date) -> AccountExport:
    """Six habits of every goal type over ten weeks, with a plan change, a pause and notes."""
    rng = random.Random(20261127)
    start = today - timedelta(days=HISTORY_DAYS)
    plan_change = today - timedelta(days=28)
    holiday = (today - timedelta(days=20), today - timedelta(days=18))
    days = [start + timedelta(days=offset) for offset in range(HISTORY_DAYS)]  # up to yesterday

    def paused(day: date) -> bool:
        return holiday[0] <= day <= holiday[1]

    def on_days(weekdays_for: Callable[[date], int], rate: float, notes: dict[int, str] | None = None):
        checkins = []
        for index, day in enumerate(days):
            planned = _planned(weekdays_for(day), day)
            if paused(day):
                continue
            if planned and rng.random() < rate:
                note = (notes or {}).get(index)
                checkins.append(ExportCheckin(date=day, done=True, note=note))
            elif not planned and rng.random() < 0.08:
                checkins.append(ExportCheckin(date=day, done=True))  # extra, never hurts the quota
        return checkins

    read = ExportHabit(
        ref=1,
        name="Read 20 pages",
        cue="after dinner",
        sort_order=0,
        color="blue",
        group_ref=2,
        schedules=[
            ExportSchedule(valid_from=start, weekdays=EVERY_DAY),
            ExportSchedule(valid_from=plan_change, weekdays=WEEKDAYS),
        ],
        checkins=on_days(lambda day: WEEKDAYS if day >= plan_change else EVERY_DAY, 0.78),
    )
    stretch = ExportHabit(
        ref=2,
        name="Stretch",
        cue="after getting up",
        sort_order=0,
        color="teal",
        group_ref=1,
        schedules=[ExportSchedule(valid_from=start, weekdays=EVERY_DAY)],
        checkins=[*on_days(lambda _day: EVERY_DAY, 0.85), ExportCheckin(date=today, done=True)],
    )
    water_checkins = []
    for day in days:
        if not paused(day):
            value = rng.choice((3, 5, 6, 7, 8, 8, 8, 9, 10))
            water_checkins.append(ExportCheckin(date=day, done=value >= 8, value=value))
    water = ExportHabit(
        ref=3,
        name="Water",
        sort_order=1,
        unit="glasses",
        color="amber",
        group_ref=1,
        schedules=[ExportSchedule(valid_from=start, weekdays=EVERY_DAY, goal_type="quantity", target=8)],
        checkins=[*water_checkins, ExportCheckin(date=today, done=False, value=3)],
    )
    run_notes = ["5 km in the rain", "New route along the river", "Slow, but done", "Personal best!"]
    run_checkins = []
    for week_start in range(0, HISTORY_DAYS, 7):
        week = [day for day in days[week_start : week_start + 7] if not paused(day)]
        for day in sorted(rng.sample(week, min(len(week), rng.choice((2, 3, 3, 4))))):
            note = run_notes.pop() if run_notes and rng.random() < 0.3 else None
            run_checkins.append(ExportCheckin(date=day, done=True, note=note))
    run = ExportHabit(
        ref=4,
        name="Run",
        sort_order=2,
        color="green",
        group_ref=1,
        schedules=[ExportSchedule(valid_from=start, weekdays=EVERY_DAY, goal_type="weekly_count", target=3)],
        checkins=run_checkins,
    )
    journal_notes = {10: "Good talk with Sam", 33: "Tired, short entry", 52: "Planned the holiday", 61: "Calm day"}
    journal = ExportHabit(
        ref=5,
        name="Journal",
        cue="before bed",
        sort_order=1,
        color="purple",
        group_ref=2,
        schedules=[ExportSchedule(valid_from=start, weekdays=MON_WED_FRI)],
        checkins=on_days(lambda _day: MON_WED_FRI, 0.7, journal_notes),
    )
    call = ExportHabit(
        ref=6,
        name="Call family",
        sort_order=3,
        color="pink",
        schedules=[ExportSchedule(valid_from=start, weekdays=EVERY_DAY, goal_type="weekly_count", target=1)],
        checkins=[
            ExportCheckin(date=day, done=True)
            for day in days
            if day.weekday() == 6 and not paused(day) and rng.random() < 0.85
        ],
    )
    habits = [stretch, water, run, read, journal, call]
    for habit in habits:
        habit.created_at = datetime.combine(start, datetime.min.time())
    return AccountExport(
        app_version=__version__,
        groups=[ExportGroup(ref=1, name="Body", sort_order=0), ExportGroup(ref=2, name="Mind", sort_order=1)],
        habits=habits,
        pauses=[ExportPause(start_on=holiday[0], end_on=holiday[1], reason="Holiday")],
    )


def check_database(db: Session) -> None:
    """Refuse a database that has other accounts: a reset would delete them."""
    others = db.scalars(select(User.username).where(User.username != DEMO_USERNAME).limit(3)).all()
    if others:
        raise ConfigError(
            "DEMO_MODE=true deletes all data every hour, but this database has other accounts "
            f"({', '.join(others)}); use a new, empty volume for the demo"
        )


def _demo_user(db: Session) -> User:
    user = AuthRepository(db).get_user_by_username(DEMO_USERNAME)
    if user is None:
        user = AuthService(AuthRepository(db)).create_user(DEMO_USERNAME, DEMO_PASSWORD, role=ROLE_USER)
    return user


def reset(db: Session, now: datetime | None = None) -> None:
    """Delete everything but the demo account and its sessions, then import fresh sample data."""
    check_database(db)
    user = _demo_user(db)
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in KEPT_TABLES:
            db.execute(delete(table))
    # Visitors may have changed the settings; the password cannot be changed in the demo
    user.password_hash = AuthService.hash_password(DEMO_PASSWORD)
    user.is_active = True
    user.timezone = None
    user.locale = None
    user.day_end_hour = 0
    user.display_name = None
    db.execute(delete(UserSession).where(UserSession.user_id != user.id))
    db.commit()
    today = user_today(user, now or datetime.now(UTC))
    import_account(db, user, build_demo(today))


def seconds_until_next_hour(now: datetime) -> float:
    # One second late on purpose, like the backups: never wake just before the hour
    return 3600 - now.minute * 60 - now.second - now.microsecond / 1_000_000 + 1


class DemoResetScheduler:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.session_factory = session_factory
        self.clock = clock
        self._task: asyncio.Task | None = None
        self._runs = ThreadRuns("demo reset")

    def run_once(self) -> None:
        db = self.session_factory()
        try:
            reset(db, self.clock())
            logger.info("Demo data reset")
        except Exception:  # noqa: BLE001 - logged; the next hour is another try
            logger.exception("Could not reset the demo data")
        finally:
            db.close()

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="demo-reset")
        logger.info("Demo mode: account %r, data reset every full hour", DEMO_USERNAME)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._runs.wait()

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(seconds_until_next_hour(self.clock()))
            await self._runs.run(self.run_once)
