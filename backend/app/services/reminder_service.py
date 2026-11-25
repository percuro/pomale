"""Reminders: at a habit's reminder time, notify the account's devices if the habit is still open.

Runs once a minute from the scheduler (see scheduler.py), outside of any request. A reminder fires
when its local time has come, it has not fired today, and it is at most GRACE old: after a short
restart missed reminders are caught up, after a long outage they are dropped instead of arriving
in a burst. last_sent_on is committed before sending, so nothing is sent twice.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.models.habit import Habit, HabitReminder
from app.models.push import PushSubscription
from app.models.user import User
from app.repositories.habit_repository import HabitRepository
from app.services.checkin_service import CheckinService
from app.services.day_service import DayInfo, WeekProgress
from app.services.i18n import resolve_locale, text
from app.services.push_service import record_result
from app.services.timezones import user_zone
from app.services.webpush.sender import PushSender

GRACE = timedelta(minutes=15)
# Well below the 4 kB a push message may carry; long lists of names are shortened
PAYLOAD_LIMIT = 3000
OPEN_STATES = ("open", "partial")

logger = logging.getLogger(__name__)


def reminder_moment(day: date, at: time, zone: ZoneInfo) -> datetime:
    """The UTC instant of a local time. A time skipped by a clock change (02:30 in spring) maps to
    the instant one hour later; a repeated one (autumn) to its first occurrence."""
    return datetime.combine(day, at, tzinfo=zone).astimezone(UTC)


def is_due(at: time, last_sent_on: date | None, now: datetime, zone: ZoneInfo) -> bool:
    today = now.astimezone(zone).date()
    if last_sent_on == today:
        return False
    # Compare in UTC: subtracting two times in the same zone ignores clock changes
    moment = reminder_moment(today, at, zone)
    now_utc = now.astimezone(UTC)
    return moment <= now_utc and now_utc - moment <= GRACE


@dataclass(frozen=True)
class OpenHabit:
    habit: Habit
    day: DayInfo
    week: WeekProgress | None


def _detail(locale: str, item: OpenHabit) -> str:
    day, habit = item.day, item.habit
    if day.goal_type == "quantity":
        values = {"value": day.value or 0, "target": day.target, "unit": habit.unit}
        return text(locale, "reminder.quantity_unit" if habit.unit else "reminder.quantity").format(**values)
    if day.goal_type == "weekly_count" and item.week is not None:
        return text(locale, "reminder.weekly").format(done=item.week.done, target=item.week.target)
    return habit.cue or text(locale, "reminder.open")


def build_payload(locale: str, items: list[OpenHabit], today: date) -> dict:
    """One notification for everything due in this minute; a "done" button only for a single
    habit that is not a quantity goal (there "done" would jump to the target)."""
    ids = "-".join(str(item.habit.id) for item in items)
    payload = {"tag": f"reminder-{ids}", "url": "/today", "habit": None}
    if len(items) == 1:
        item = items[0]
        payload |= {"title": item.habit.name, "body": _detail(locale, item)}
        if item.day.goal_type != "quantity":
            payload["habit"] = {"id": item.habit.id, "date": today.isoformat()}
        return payload
    names = [item.habit.name for item in items]
    payload |= {"title": text(locale, "reminder.several").format(count=len(items)), "body": ", ".join(names)}
    while len(json.dumps(payload, ensure_ascii=False).encode()) > PAYLOAD_LIMIT and len(names) > 1:
        names.pop()
        payload["body"] = ", ".join(names) + " …"
    return payload


class ReminderService:
    def __init__(self, session_factory: Callable[[], Session], sender: PushSender):
        self.session_factory = session_factory
        self.sender = sender

    def run_due(self, now: datetime) -> int:
        """Send what is due at `now` (aware). Returns the number of notifications sent."""
        db = self.session_factory()
        try:
            jobs = self._collect(db, now)
            return sum(self._send(db, user_id, payload, now) for user_id, payload in jobs)
        finally:
            db.close()

    def _collect(self, db: Session, now: datetime) -> list[tuple[int, dict]]:
        has_device = exists().where(PushSubscription.user_id == User.id)
        rows = db.execute(
            select(HabitReminder, Habit, User)
            .join(Habit, HabitReminder.habit_id == Habit.id)
            .join(User, Habit.user_id == User.id)
            .where(Habit.archived_on.is_(None), User.is_active.is_(True), has_device)
            .options(selectinload(Habit.schedules))
            .order_by(User.id, Habit.sort_order, Habit.id)
        ).all()
        by_user: dict[int, tuple[User, list[tuple[HabitReminder, Habit]]]] = {}
        for reminder, habit, user in rows:
            by_user.setdefault(user.id, (user, []))[1].append((reminder, habit))

        jobs = []
        checkins = CheckinService(HabitRepository(db))
        for user, reminders in by_user.values():
            zone = user_zone(user)
            today = now.astimezone(zone).date()
            due = [(r, h) for r, h in reminders if is_due(r.time, r.last_sent_on, now, zone)]
            if not due:
                continue
            for reminder, _ in due:
                reminder.last_sent_on = today
            db.commit()
            habits = list({habit.id: habit for _, habit in due}.values())
            items = []
            for habit in habits:
                evaluation = checkins.evaluate(habit, today, today, today)
                if evaluation.days[0].state in OPEN_STATES:
                    items.append(OpenHabit(habit, evaluation.days[0], evaluation.week))
            if items:
                jobs.append((user.id, build_payload(resolve_locale(user, None), items, today)))
        return jobs

    def _send(self, db: Session, user_id: int, payload: dict, now: datetime) -> int:
        body = json.dumps(payload, ensure_ascii=False).encode()
        subscriptions = db.scalars(select(PushSubscription).where(PushSubscription.user_id == user_id)).all()
        sent = 0
        for subscription in subscriptions:
            result = self.sender.send(
                subscription.endpoint, subscription.p256dh, subscription.auth, body, topic="reminders"
            )
            if result.outcome == "gone":
                db.delete(subscription)
            else:
                record_result(subscription, result, now.astimezone(UTC).replace(tzinfo=None))
                sent += result.outcome == "ok"
        db.commit()
        return sent
