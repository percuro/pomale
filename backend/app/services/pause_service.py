from datetime import timedelta

from app.errors import AppError
from app.models.habit import HabitPause
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import PauseCreate, PauseUpdate
from app.services.habit_service import HabitService

MAX_PAUSE_DAYS = 366


class PauseService:
    """Pauses (holidays, illness): days that are not due. They may lie in the past too."""

    def __init__(self, repository: HabitRepository):
        self.repository = repository

    def get(self, pause_id: int, user_id: int) -> HabitPause:
        pause = self.repository.get_pause(pause_id, user_id)
        if pause is None:
            raise AppError(404, "pause.not_found", "Pause not found")
        return pause

    def _check(self, pause: HabitPause, user_id: int) -> None:
        if pause.habit_id is not None:
            HabitService(self.repository).get(pause.habit_id, user_id)
        if pause.end_on < pause.start_on:
            raise AppError(422, "pause.end_before_start", "The pause ends before it starts")
        if pause.end_on - pause.start_on >= timedelta(days=MAX_PAUSE_DAYS):
            raise AppError(
                422, "pause.too_long", f"A pause lasts at most {MAX_PAUSE_DAYS} days", max_days=MAX_PAUSE_DAYS
            )

    def create(self, user_id: int, data: PauseCreate) -> HabitPause:
        pause = HabitPause(
            user_id=user_id, habit_id=data.habit_id, start_on=data.start_on, end_on=data.end_on, reason=data.reason
        )
        self._check(pause, user_id)
        self.repository.add_object(pause)
        return pause

    def update(self, pause_id: int, user_id: int, data: PauseUpdate) -> HabitPause:
        pause = self.get(pause_id, user_id)
        fields = data.model_fields_set
        if "habit_id" in fields:
            pause.habit_id = data.habit_id
        if "start_on" in fields and data.start_on is not None:
            pause.start_on = data.start_on
        if "end_on" in fields and data.end_on is not None:
            pause.end_on = data.end_on
        if "reason" in fields:
            pause.reason = data.reason
        try:
            self._check(pause, user_id)
        except AppError:
            self.repository.db.rollback()
            raise
        self.repository.commit()
        self.repository.db.refresh(pause)
        return pause

    def delete(self, pause_id: int, user_id: int) -> None:
        self.repository.delete_object(self.get(pause_id, user_id))
