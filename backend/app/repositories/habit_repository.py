from datetime import date

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.habit import Checkin, Habit, HabitGroup, HabitPause, HabitSchedule


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

    def upsert_schedule(
        self, habit: Habit, valid_from: date, weekdays: int, goal_type: str = "days", target: int | None = None
    ) -> None:
        for schedule in habit.schedules:
            if schedule.valid_from == valid_from:
                schedule.weekdays = weekdays
                schedule.goal_type = goal_type
                schedule.target = target
                break
        else:
            habit.schedules.append(
                HabitSchedule(valid_from=valid_from, weekdays=weekdays, goal_type=goal_type, target=target)
            )

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

    def pauses_overlapping(self, user_id: int, start: date, end: date) -> list[HabitPause]:
        """The account's pauses that touch start..end, for all habits and single ones."""
        return list(
            self.db.scalars(
                select(HabitPause)
                .where(HabitPause.user_id == user_id, HabitPause.start_on <= end, HabitPause.end_on >= start)
                .order_by(HabitPause.start_on, HabitPause.id)
            )
        )

    def get_checkin(self, habit_id: int, day: date) -> Checkin | None:
        return self.db.get(Checkin, (habit_id, day))

    def add_to_value(self, habit_id: int, day: date, amount: int, target: int, maximum: int) -> None:
        """Atomically add to a quantity day: two shortcut calls at once add up, nothing is lost."""
        current = func.coalesce(Checkin.value, case((Checkin.done.is_(True), target), else_=0))
        statement = (
            update(Checkin)
            .where(Checkin.habit_id == habit_id, Checkin.local_date == day)
            .values(value=func.min(current + amount, maximum), done=True, version=Checkin.version + 1, last_op_id=None)
            .execution_options(synchronize_session=False)
        )
        if self.db.execute(statement).rowcount:
            self.db.commit()
            return
        self.db.rollback()
        checkin = Checkin(habit_id=habit_id, local_date=day, done=True, value=min(amount, maximum), version=1)
        if not self.insert_checkin(checkin):
            # Someone else created the entry in the meantime: add to it
            self.add_to_value(habit_id, day, amount, target, maximum)

    def insert_checkin(self, checkin: Checkin) -> bool:
        """Insert an entry. False if a concurrent request was faster."""
        self.db.add(checkin)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            return False
        return True

    # Groups

    def list_groups(self, user_id: int) -> list[HabitGroup]:
        return list(
            self.db.scalars(
                select(HabitGroup).where(HabitGroup.user_id == user_id).order_by(HabitGroup.sort_order, HabitGroup.id)
            )
        )

    def get_group(self, group_id: int, user_id: int) -> HabitGroup | None:
        return self.db.scalars(
            select(HabitGroup).where(HabitGroup.id == group_id, HabitGroup.user_id == user_id)
        ).first()

    def group_name_taken(self, user_id: int, name: str, except_id: int | None = None) -> bool:
        query = select(HabitGroup.id).where(HabitGroup.user_id == user_id, func.lower(HabitGroup.name) == name.lower())
        if except_id is not None:
            query = query.where(HabitGroup.id != except_id)
        return self.db.scalar(query) is not None

    def next_group_sort_order(self, user_id: int) -> int:
        current = self.db.scalar(select(func.max(HabitGroup.sort_order)).where(HabitGroup.user_id == user_id))
        return (current or 0) + 1

    def add_object(self, obj) -> None:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)

    def delete_object(self, obj) -> None:
        self.db.delete(obj)
        self.db.commit()

    # Pauses

    def list_pauses(self, user_id: int) -> list[HabitPause]:
        return list(
            self.db.scalars(
                select(HabitPause)
                .where(HabitPause.user_id == user_id)
                .order_by(HabitPause.start_on.desc(), HabitPause.id.desc())
            )
        )

    def get_pause(self, pause_id: int, user_id: int) -> HabitPause | None:
        return self.db.scalars(
            select(HabitPause).where(HabitPause.id == pause_id, HabitPause.user_id == user_id)
        ).first()
