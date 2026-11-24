from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.habit import Checkin, Habit, HabitSchedule


class HabitRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_user(self, user_id: int, include_archived: bool = False) -> list[Habit]:
        query = (
            select(Habit)
            .options(selectinload(Habit.schedules))
            .where(Habit.user_id == user_id)
            .order_by(Habit.sort_order, Habit.id)
        )
        if not include_archived:
            query = query.where(Habit.archived_on.is_(None))
        return list(self.db.scalars(query))

    def list_active_between(self, user_id: int, start: date) -> list[Habit]:
        """Active habits plus those archived on or after `start`."""
        query = (
            select(Habit)
            .options(selectinload(Habit.schedules))
            .where(Habit.user_id == user_id)
            .where(or_(Habit.archived_on.is_(None), Habit.archived_on >= start))
            .order_by(Habit.sort_order, Habit.id)
        )
        return list(self.db.scalars(query))

    def get_for_user(self, habit_id: int, user_id: int) -> Habit | None:
        return self.db.scalars(
            select(Habit).options(selectinload(Habit.schedules)).where(Habit.id == habit_id, Habit.user_id == user_id)
        ).first()

    def next_sort_order(self, user_id: int) -> int:
        current = self.db.scalar(select(func.max(Habit.sort_order)).where(Habit.user_id == user_id))
        return (current or 0) + 1

    def add(self, habit: Habit) -> Habit:
        self.db.add(habit)
        self.db.commit()
        self.db.refresh(habit)
        return habit

    def upsert_schedule(self, habit: Habit, valid_from: date, weekdays: int) -> None:
        for schedule in habit.schedules:
            if schedule.valid_from == valid_from:
                schedule.weekdays = weekdays
                break
        else:
            habit.schedules.append(HabitSchedule(valid_from=valid_from, weekdays=weekdays))

    def delete_schedules_after(self, habit: Habit, day: date) -> None:
        for schedule in [s for s in habit.schedules if s.valid_from > day]:
            habit.schedules.remove(schedule)

    def commit(self, habit: Habit | None = None) -> None:
        self.db.commit()
        if habit is not None:
            self.db.refresh(habit)

    def checkins_between(self, habit_ids: list[int], start: date, end: date) -> list[Checkin]:
        if not habit_ids:
            return []
        return list(
            self.db.scalars(
                select(Checkin).where(
                    Checkin.habit_id.in_(habit_ids),
                    Checkin.local_date >= start,
                    Checkin.local_date <= end,
                )
            )
        )

    def get_checkin(self, habit_id: int, day: date) -> Checkin | None:
        return self.db.get(Checkin, (habit_id, day))

    def insert_checkin(self, checkin: Checkin) -> bool:
        """Insert an entry. False if a concurrent request was faster."""
        self.db.add(checkin)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return False
        return True
