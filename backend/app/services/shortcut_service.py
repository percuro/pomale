import hashlib
import secrets
from datetime import date

from fastapi import Request

from app.errors import AppError
from app.models.shortcut_token import ShortcutToken
from app.repositories.habit_repository import HabitRepository
from app.repositories.shortcut_repository import ShortcutRepository
from app.schemas.shortcut import ShortcutCheckinRead
from app.services.auth_service import utcnow
from app.services.checkin_service import CheckinService
from app.services.login_rate_limiter import LoginRateLimiter

TOKEN_PREFIX = "ht_"
# Limit failed attempts with wrong keys per IP (same logic as the login limit)
shortcut_rate_limiter = LoginRateLimiter()


def _unauthorized() -> AppError:
    return AppError(401, "shortcut.invalid_token", "Key is invalid or revoked", headers={"WWW-Authenticate": "Bearer"})


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


class ShortcutService:
    def __init__(self, repository: ShortcutRepository, habits: HabitRepository):
        self.repository = repository
        self.habits = habits

    def create(self, habit_id: int, label: str) -> tuple[ShortcutToken, str]:
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        token = self.repository.add(
            ShortcutToken(habit_id=habit_id, label=label.strip() or "iPhone", token_hash=hash_token(raw))
        )
        return token, raw

    def revoke(self, habit_id: int, token_id: int) -> None:
        token = self.repository.get_for_habit(token_id, habit_id)
        if token is None:
            raise AppError(404, "shortcut.token_not_found", "Key not found")
        self.repository.revoke(token, utcnow())

    def check_in_today(self, request: Request, habit_id: int, done: bool, today: date) -> ShortcutCheckinRead:
        ip_address = request.client.host if request.client else "unknown"
        shortcut_rate_limiter.check("shortcut", ip_address)
        raw = bearer_token(request)
        token = self.repository.get_by_hash(hash_token(raw)) if raw else None
        if token is None or token.revoked_at is not None:
            shortcut_rate_limiter.record_failure("shortcut", ip_address)
            raise _unauthorized()
        if token.habit_id != habit_id:
            raise AppError(403, "shortcut.wrong_habit", "This key belongs to another habit")
        if not done:
            raise AppError(422, "shortcut.done_only", "The shortcut can only mark a habit as done")
        habit = token.habit
        if habit.archived_on is not None:
            raise AppError(409, "habit.archived", "The habit is archived")

        before = self.habits.get_checkin(habit.id, today)
        already = bool(before and before.done)
        result = CheckinService(self.habits).set_state(habit, today, True, today, op_id=None, base_version=None)
        self.repository.touch(token, utcnow())
        status_text = "Bereits erledigt" if already else "Heute erledigt"
        return ShortcutCheckinRead(
            habit_id=habit.id,
            habit_name=habit.name,
            date=result.date,
            done=result.done,
            status=status_text,
            message=f"{habit.name}: {status_text}",
        )
