from datetime import date, timedelta

from app.errors import AppError
from app.models.habit import Habit, HabitGroup, HabitReminder, HabitSchedule
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import (
    HabitCreate,
    HabitOrder,
    HabitRead,
    HabitUpdate,
    ScheduleRead,
    ScheduleUpdate,
    check_goal,
)
from app.services.day_service import Plan, plan_for


def last_active_plan(habit: Habit) -> Plan | None:
    """The last plan with planned weekdays (archiving adds one without)."""
    active = [s for s in habit.schedules if s.weekdays]
    if not active:
        return None
    last: HabitSchedule = active[-1]
    return Plan(last.weekdays, last.goal_type, last.target)


def shown_plan(habit: Habit, today: date) -> Plan:
    """The plan in effect today; for archived or not yet started habits the last or upcoming one."""
    current = plan_for(habit.schedules, today)
    if current.weekdays:
        return current
    return last_active_plan(habit) or current


def habit_read(habit: Habit, today: date) -> HabitRead:
    plan = shown_plan(habit, today)
    return HabitRead(
        id=habit.id,
        name=habit.name,
        cue=habit.cue,
        sort_order=habit.sort_order,
        archived_on=habit.archived_on,
        weekdays=plan.weekdays,
        goal_type=plan.goal_type,
        target=plan.target,
        unit=habit.unit,
        color=habit.color,
        group_id=habit.group_id,
        reminders=[reminder.time.strftime("%H:%M") for reminder in habit.reminders],
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

    def group(self, group_id: int | None, user_id: int) -> HabitGroup | None:
        if group_id is None:
            return None
        group = self.repository.get_group(group_id, user_id)
        if group is None:
            raise AppError(404, "group.not_found", "Group not found")
        return group

    def list(self, user_id: int, include_archived: bool) -> list[Habit]:
        return self.repository.list_for_user(user_id, include_archived)

    def create(self, user_id: int, data: HabitCreate, today: date) -> Habit:
        self.group(data.group_id, user_id)
        habit = Habit(
            user_id=user_id,
            name=data.name,
            cue=data.cue,
            unit=data.unit,
            color=data.color,
            group_id=data.group_id,
            sort_order=self.repository.next_sort_order(user_id),
            reminders=[HabitReminder(time=value) for value in data.reminders],
        )
        self.repository.upsert_schedule(habit, data.start_on or today, data.weekdays, data.goal_type, data.target)
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
        if "unit" in fields:
            habit.unit = data.unit
        if "color" in fields:
            habit.color = data.color
        if "group_id" in fields:
            self.group(data.group_id, user_id)
            habit.group_id = data.group_id
        if "reminders" in fields and data.reminders is not None:
            # Unchanged times keep last_sent_on, so editing a habit does not fire them again today
            kept = {reminder.time: reminder for reminder in habit.reminders}
            habit.reminders = [kept.get(value) or HabitReminder(time=value) for value in data.reminders]
        self.repository.commit(habit)
        return habit

    def set_schedule(self, habit_id: int, user_id: int, data: ScheduleUpdate, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is not None:
            raise AppError(409, "habit.archived", "Reactivate the archived habit first")
        valid_from = data.valid_from or today
        if data.goal_type is None:
            # Only the weekdays change; the goal type and target stay as they are
            current = plan_for(habit.schedules, valid_from)
            if not current.weekdays:
                current = last_active_plan(habit) or current
            goal_type, target = current.goal_type, current.target
            weekdays = 127 if goal_type == "weekly_count" else data.weekdays
        else:
            goal_type, target, weekdays = data.goal_type, data.target, data.weekdays
        try:
            check_goal(goal_type, target)
        except ValueError as error:
            raise AppError(422, "habit.invalid_goal", str(error)) from error
        self.repository.upsert_schedule(habit, valid_from, weekdays, goal_type, target)
        self.repository.commit(habit)
        return habit

    def archive(self, habit_id: int, user_id: int, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is None:
            # Today stays as planned; not planned from tomorrow on. History is kept.
            plan = plan_for(habit.schedules, today)
            habit.archived_on = today
            self.repository.delete_schedules_after(habit, today)
            self.repository.upsert_schedule(habit, today + timedelta(days=1), 0, plan.goal_type, plan.target)
            self.repository.commit(habit)
        return habit

    def unarchive(self, habit_id: int, user_id: int, today: date) -> Habit:
        habit = self.get(habit_id, user_id)
        if habit.archived_on is not None:
            plan = last_active_plan(habit) or Plan(127)
            habit.archived_on = None
            self.repository.delete_schedules_after(habit, today)
            if plan_for(habit.schedules, today) != plan:
                self.repository.upsert_schedule(habit, today, plan.weekdays, plan.goal_type, plan.target)
            self.repository.commit(habit)
        return habit

    def reorder(self, user_id: int, data: HabitOrder) -> "list[Habit]":
        """Put the listed habits first, in this order and into the given groups, in one commit."""
        ids = [item.id for item in data.habits]
        if len(set(ids)) != len(ids):
            raise AppError(422, "habit.order_duplicate", "A habit is listed twice")
        habits = {h.id: h for h in self.repository.list_for_user(user_id, include_archived=True)}
        groups = {g.id for g in self.repository.list_groups(user_id)}
        for item in data.habits:
            if item.id not in habits:
                raise AppError(404, "habit.not_found", "Habit not found")
            if item.group_id is not None and item.group_id not in groups:
                raise AppError(404, "group.not_found", "Group not found")
        listed = [habits[i] for i in ids]
        rest = [h for h in habits.values() if h.id not in set(ids)]
        for position, habit in enumerate(listed + rest, start=1):
            habit.sort_order = position
        for item in data.habits:
            habits[item.id].group_id = item.group_id
        self.repository.commit()
        return self.repository.list_for_user(user_id, include_archived=False)
