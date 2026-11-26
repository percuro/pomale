"""Reminders: at a habit's reminder time, notify the account's devices if the habit is still open.

Runs once a minute from the scheduler (see scheduler.py), outside of any request. A reminder fires
when its local time has come, it has not fired for that day, and it is at most GRACE old: after a
short restart missed reminders are caught up, after a long outage they are dropped instead of
arriving in a burst. last_sent_on is committed before sending, so nothing is sent twice.

Days are the account's own days: with a day end after midnight, a reminder time before the day
end belongs to the day that is ending (00:30 with a day end of 02:00 reminds of "yesterday").
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
from app.services.day_service import DayInfo, WeekProgress, today_in
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


def reminder_moment_on(day: date, at: time, zone: ZoneInfo, day_end_hour: int = 0) -> datetime:
    """The UTC instant of a reminder that belongs to `day`: a time before the day end falls on the
    next calendar day, because that is where the account's day still runs."""
    calendar_day = day + timedelta(days=1) if at.hour < day_end_hour else day
    return reminder_moment(calendar_day, at, zone)


def due_on(at: time, last_sent_on: date | None, now: datetime, zone: ZoneInfo, day_end_hour: int = 0) -> date | None:
    """The day a reminder fires for at `now`, or None. The day before is checked too, so that a
    reminder shortly before the day end is still caught up just after it."""
    now_utc = now.astimezone(UTC)
    today = today_in(zone, now, day_end_hour)
    for day in (today, today - timedelta(days=1)):
        # Sent for this day or a later one: an earlier day never fires afterwards
        if last_sent_on is not None and last_sent_on >= day:
            continue
        # Compare in UTC: subtracting two times in the same zone ignores clock changes
        moment = reminder_moment_on(day, at, zone, day_end_hour)
        if moment <= now_utc and now_utc - moment <= GRACE:
            return day
    return None


def is_due(at: time, last_sent_on: date | None, now: datetime, zone: ZoneInfo, day_end_hour: int = 0) -> bool:
    return due_on(at, last_sent_on, now, zone, day_end_hour) is not None


@dataclass(frozen=True)
class OpenHabit:
    habit: Habit
    day: DayInfo
    week: WeekProgress | None
    # Version of today's entry (0 = none): the done button sends it, like the offline queue
    version: int = 0


def _detail(locale: str, item: OpenHabit) -> str:
    day, habit = item.day, item.habit
    if day.goal_type == "quantity":
        values = {"value": day.value or 0, "target": day.target, "unit": habit.unit}
        return text(locale, "reminder.quantity_unit" if habit.unit else "reminder.quantity").format(**values)
    if day.goal_type == "weekly_count" and item.week is not None:
        return text(locale, "reminder.weekly").format(done=item.week.done, target=item.week.target)
    return habit.cue or text(locale, "reminder.open")


def build_payload(locale: str, items: list[OpenHabit], today: date, user_id: int) -> dict:
    """One notification for everything due in this minute; a "done" button only for a single
    habit that is not a quantity goal (there "done" would jump to the target)."""
    ids = "-".join(str(item.habit.id) for item in items)
    payload = {"tag": f"reminder-{ids}", "url": "/today", "habit": None}
    if len(items) == 1:
        item = items[0]
        payload |= {"title": item.habit.name, "body": _detail(locale, item)}
        if item.day.goal_type != "quantity":
            payload["habit"] = {
                "id": item.habit.id,
                "date": today.isoformat(),
                "version": item.version,
                "user": user_id,
            }
            payload["done_label"] = text(locale, "reminder.done_action")
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
            day_end_hour = user.day_end_hour or 0
            today = today_in(zone, now, day_end_hour)
            due = []
            for reminder, habit in reminders:
                day = due_on(reminder.time, reminder.last_sent_on, now, zone, day_end_hour)
                if day is not None:
                    due.append((reminder, habit, day))
            if not due:
                continue
            for reminder, _, day in due:
                reminder.last_sent_on = day
            db.commit()
            # Usually one day; a reminder caught up from the day before comes as its own notification
            for day in sorted({day for _, _, day in due}):
                habits = list({habit.id: habit for _, habit, due_day in due if due_day == day}.values())
                items = []
                for habit in habits:
                    evaluation = checkins.evaluate(habit, day, day, today)
                    if evaluation.days[0].state in OPEN_STATES:
                        entry = checkins.repository.get_checkin(habit.id, day)
                        version = entry.version if entry else 0
                        items.append(OpenHabit(habit, evaluation.days[0], evaluation.week, version))
                if items:
                    jobs.append((user.id, build_payload(resolve_locale(user, None), items, day, user.id)))
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
