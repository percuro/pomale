"""The iOS shortcut: check off "today" with an API key for one habit.

Since 0.10 a shortcut key is an API token with scope "checkin" for exactly that habit; who may
call is decided in token_service before this runs. The per-habit key endpoints stay for the
shortcut panel on the habits page.
"""

from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.api_token import SCOPE_CHECKIN, ApiToken
from app.models.habit import QUANTITY_TARGET_MAX
from app.models.user import User
from app.repositories.habit_repository import HabitRepository
from app.schemas.shortcut import ShortcutCheckinRead
from app.services.checkin_service import CheckinService
from app.services.day_service import plan_for
from app.services.habit_service import HabitService
from app.services.i18n import resolve_locale, text
from app.services.timezones import user_today
from app.services.token_service import TokenService


def is_shortcut_key(token: ApiToken, habit_id: int) -> bool:
    """A key that does what a shortcut key does: check off this one habit, nothing else."""
    return token.scope_set == {SCOPE_CHECKIN} and token.habit_ids == [habit_id]


class ShortcutService:
    def __init__(self, db: Session):
        self.db = db
        self.habits = HabitRepository(db)
        self.tokens = TokenService(db)

    def list_for(self, user: User, habit_id: int) -> list[ApiToken]:
        return sorted((t for t in self.tokens.list_for(user) if is_shortcut_key(t, habit_id)), key=lambda t: t.id)

    def create(self, user: User, habit_id: int, label: str) -> tuple[ApiToken, str]:
        return self.tokens.create(user, label.strip() or "iPhone", [SCOPE_CHECKIN], [habit_id])

    def revoke(self, user: User, habit_id: int, token_id: int) -> None:
        token = self.tokens.get(user, token_id)
        if not is_shortcut_key(token, habit_id):
            raise AppError(404, "token.not_found", "Key not found")
        self.tokens.revoke(user, token_id)

    def check_in_today(
        self, request: Request, user: User, habit_id: int, done: bool, now: datetime, amount: int | None = None
    ) -> ShortcutCheckinRead:
        habit = HabitService(self.habits).get(habit_id, user.id)
        if not done:
            raise AppError(422, "shortcut.done_only", "The shortcut can only mark a habit as done")
        if habit.archived_on is not None:
            raise AppError(409, "habit.archived", "The habit is archived")
        # "Today" of the habit's owner, wherever the phone or the server is
        today = user_today(user, now)

        locale = resolve_locale(user, request)
        checkins = CheckinService(self.habits)
        plan = plan_for(habit.schedules, today)
        if plan.goal_type == "quantity":
            target = plan.target or 1
            self.habits.add_to_value(habit.id, today, amount or 1, target, QUANTITY_TARGET_MAX)
            result = checkins.read_day(habit, today, today)
            status_text = text(locale, "shortcut.counted").format(value=result.value, target=target)
            if habit.unit:
                status_text = f"{status_text} {habit.unit}"
            return ShortcutCheckinRead(
                habit_id=habit.id,
                habit_name=habit.name,
                date=result.date,
                done=result.done,
                result="counted",
                status=status_text,
                message=f"{habit.name}: {status_text}",
                value=result.value,
                target=target,
            )

        before = self.habits.get_checkin(habit.id, today)
        already = bool(before and before.done)
        result = checkins.set_state(habit, today, today, done=True)
        outcome = "already_done" if already else "done"
        status_text = text(locale, f"shortcut.{outcome}")
        return ShortcutCheckinRead(
            habit_id=habit.id,
            habit_name=habit.name,
            date=result.date,
            done=result.done,
            result=outcome,
            status=status_text,
            message=f"{habit.name}: {status_text}",
        )
