from datetime import date, timedelta

from app.errors import AppError
from app.models.habit import Habit
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import HabitCreate, HabitRead, HabitUpdate, ScheduleRead, ScheduleUpdate
from app.services.day_service import weekdays_for


def habit_read(habit: Habit, today: date) -> HabitRead:
    current = weekdays_for(habit.schedules, today)
    if current == 0:
        # archived or not started yet: show the last or upcoming planned weekdays
        non_zero = [s.weekdays for s in habit.schedules if s.weekdays]
        current = non_zero[-1] if non_zero else 0
    return HabitRead(
        id=habit.id,
        name=habit.name,
        cue=habit.cue,
        sort_order=habit.sort_order,
        archived_on=habit.archived_on,
        weekdays=current,
        schedules=[ScheduleRead.model_validate(s) for s in habit.schedules],
    )


class HabitService:
    def __init__(self, repository: HabitRepository):
        self.repository = repository

    def get(self, habit_id: int, user_id: int) -> Habit:
        habit = self.repository.get_for_user(habit_id, user_id)
        if habit is None:
            raise AppError(404, "habit.not_found", "Habit not found")
        return habit

    def list(self, user_id: int, include_archived: bool) -> list[Habit]:
        return self.repository.list_for_user(user_id, include_archived)

    def create(self, user_id: int, data: HabitCreate, today: date) -> Habit:
        habit = Habit(
            user_id=user_id,
            name=data.name,
            cue=data.cue,
            sort_order=self.repository.next_sort_order(user_id),
        )
        self.repository.upsert_schedule(habit, data.start_on or today, data.weekdays)
        return self.repository.add(habit)

    def update(self, habit_id: int, user_id: int, data: HabitUpdate) -> Habit:
        habit = self.get(habit_id, user_id)
        fields = data.model_fields_set
        if "name" in fields and data.name is not None:
            habit.name = data.name
        if "cue" in fields:
            habit.cue = data.cue
        if "sort_order" in fields and data.sort_order is not None:
            habit.sort_order = data.sort_order
        self.repository.commit(habit)
        return habit

    def set_schedule(self, habit_id: int, user_id: int, data: ScheduleUpdate, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is not None:
            raise AppError(409, "habit.archived", "Reactivate the archived habit first")
        self.repository.upsert_schedule(habit, data.valid_from or today, data.weekdays)
        self.repository.commit(habit)
        return habit

    def archive(self, habit_id: int, user_id: int, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is None:
            # Today stays as planned; not planned from tomorrow on. History is kept.
            habit.archived_on = today
            self.repository.delete_schedules_after(habit, today)
            self.repository.upsert_schedule(habit, today + timedelta(days=1), 0)
            self.repository.commit(habit)
        return habit

    def unarchive(self, habit_id: int, user_id: int, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is not None:
            non_zero = [s.weekdays for s in habit.schedules if s.weekdays]
            weekdays = non_zero[-1] if non_zero else 127
            habit.archived_on = None
            self.repository.delete_schedules_after(habit, today)
            if weekdays_for(habit.schedules, today) != weekdays:
                self.repository.upsert_schedule(habit, today, weekdays)
            self.repository.commit(habit)
        return habit
