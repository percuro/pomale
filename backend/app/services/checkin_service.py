from datetime import date, timedelta

from app.errors import AppError
from app.models.habit import Checkin, Habit, HabitPause
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import (
    CheckinRead,
    DayRead,
    DaysRead,
    GroupRead,
    HabitDaysRead,
    HistoryDayRead,
    HistoryHabitRead,
    HistoryRead,
    HistoryWeekRead,
    NoteRead,
    QuotaRead,
    WeekRead,
)
from app.services.day_service import Entry, Evaluation, evaluate_range, plan_for, week_start
from app.services.habit_service import shown_plan

MAX_RANGE_DAYS = 62
MAX_HISTORY_DAYS = 366
HISTORY_WEEKS = 12


class CheckinService:
    def __init__(self, repository: HabitRepository):
        self.repository = repository

    def set_state(
        self,
        habit: Habit,
        day: date,
        today: date,
        *,
        done: bool | None = None,
        value: int | None = None,
        op_id: str | None = None,
        base_version: int | None = None,
    ) -> CheckinRead:
        """Set the state (never toggle). Repeating a request creates no second entry.

        Days and weekly goals take `done`. Quantity goals take `value`; `done` sets the value to
        the target or 0. With base_version (offline queue): if the target state is already
        there, that counts as success. If the entry changed since base_version, answer 409
        with the server state instead of silently overwriting it.
        """
        if day > today:
            raise AppError(422, "checkin.future_day", "Future days cannot be checked off")
        plan = plan_for(habit.schedules, day)
        quantity = plan.goal_type == "quantity"
        if value is not None and not quantity:
            raise AppError(422, "checkin.value_not_allowed", "Only quantity goals take a value")
        if quantity and value is None:
            value = (plan.target or 1) if done else 0

        checkin = self.repository.get_checkin(habit.id, day)
        current_version = checkin.version if checkin else 0
        if quantity:
            wanted: bool | int = value
            current: bool | int = _value_of(checkin, plan.target)
        else:
            wanted = bool(done)
            current = bool(checkin and checkin.done)
        if current == wanted:
            return self._read(habit, day, checkin, today)
        if base_version is not None and base_version != current_version:
            raise AppError(
                409,
                "checkin.conflict",
                "The entry was changed on another device in the meantime",
                server=self._read(habit, day, checkin, today).model_dump(mode="json")
                | {"updated_at": checkin.updated_at.isoformat() + "Z" if checkin else None},
            )
        new_done = bool(value) if quantity else bool(done)
        new_value = value if quantity else (checkin.value if checkin else None)
        if checkin is None:
            # Concurrent creation (double tap): one insert wins, the other reads its entry
            inserted = self.repository.insert_checkin(
                Checkin(habit_id=habit.id, local_date=day, done=new_done, value=new_value, version=1, last_op_id=op_id)
            )
            checkin = self.repository.get_checkin(habit.id, day)
            if not inserted:
                return self.set_state(habit, day, today, done=done, value=value, op_id=op_id, base_version=base_version)
        else:
            checkin.done = new_done
            checkin.value = new_value
            checkin.version += 1
            checkin.last_op_id = op_id
            self.repository.commit()
        return self._read(habit, day, checkin, today)

    def read_day(self, habit: Habit, day: date, today: date) -> CheckinRead:
        return self._read(habit, day, self.repository.get_checkin(habit.id, day), today)

    def set_note(self, habit: Habit, day: date, note: str | None, today: date) -> NoteRead:
        """Notes are last-write-wins and never change `version`, so they cause no sync conflicts."""
        if day > today:
            raise AppError(422, "note.future_day", "Future days cannot have a note")
        checkin = self.repository.get_checkin(habit.id, day)
        if checkin is None:
            if note is not None:
                # version 0: still "no state" for the offline queue's base_version
                inserted = self.repository.insert_checkin(
                    Checkin(habit_id=habit.id, local_date=day, done=False, version=0, note=note)
                )
                if not inserted:
                    return self.set_note(habit, day, note, today)
        elif checkin.note != note:
            checkin.note = note
            self.repository.commit()
        return NoteRead(habit_id=habit.id, date=day, note=note)

    def evaluate(self, habit: Habit, start: date, end: date, today: date) -> Evaluation:
        """One habit over start..end, loading the whole weeks around it."""
        first, last = _whole_weeks(start, end)
        checkins = self.repository.checkins_between([habit.id], first, last)
        pauses = _pauses_for(habit, self.repository.pauses_overlapping(habit.user_id, first, last))
        return evaluate_range(habit.schedules, _entries(checkins), pauses, start, end, today)

    def _read(self, habit: Habit, day: date, checkin: Checkin | None, today: date) -> CheckinRead:
        # The state of one day can depend on its week (weekly goals)
        info = self.evaluate(habit, day, day, today).days[0]
        return CheckinRead(
            habit_id=habit.id,
            date=day,
            done=info.done,
            state=info.state,
            version=checkin.version if checkin else 0,
            value=info.value,
        )

    def days(self, user_id: int, start: date, end: date, today: date, timezone: str) -> DaysRead:
        if end < start:
            raise AppError(422, "range.end_before_start", "The end date is before the start date")
        if (end - start) > timedelta(days=MAX_RANGE_DAYS):
            raise AppError(422, "range.too_long", f"At most {MAX_RANGE_DAYS} days at once", max_days=MAX_RANGE_DAYS)
        habits = self.repository.list_active_between(user_id, start)
        first, last = _whole_weeks(start, end)
        checkins = self.repository.checkins_between([h.id for h in habits], first, last)
        pauses = self.repository.pauses_overlapping(user_id, first, last)
        by_habit: dict[int, dict[date, Checkin]] = {}
        for checkin in checkins:
            by_habit.setdefault(checkin.habit_id, {})[checkin.local_date] = checkin

        result = []
        for habit in habits:
            entries = by_habit.get(habit.id, {})
            evaluation = evaluate_range(
                habit.schedules, _entries(entries.values()), _pauses_for(habit, pauses), start, end, today
            )
            q = evaluation.quota
            plan = shown_plan(habit, today)
            result.append(
                HabitDaysRead(
                    id=habit.id,
                    name=habit.name,
                    cue=habit.cue,
                    archived=habit.archived_on is not None,
                    goal_type=plan.goal_type,
                    target=plan.target,
                    unit=habit.unit,
                    color=habit.color,
                    group_id=habit.group_id,
                    days=[
                        DayRead(
                            date=info.date,
                            state=info.state,
                            planned=info.planned,
                            done=info.done,
                            version=entries[info.date].version if info.date in entries else 0,
                            goal_type=info.goal_type,
                            target=info.target,
                            paused=info.paused,
                            value=info.value,
                            note=entries[info.date].note if info.date in entries else None,
                        )
                        for info in evaluation.days
                    ],
                    quota=QuotaRead(done=q.done, due=q.due),
                    week=WeekRead(**vars(evaluation.week)) if evaluation.week else None,
                )
            )
        groups = [GroupRead.model_validate(g) for g in self.repository.list_groups(user_id)]
        return DaysRead(today=today, timezone=timezone, start=start, end=end, groups=groups, habits=result)

    def history(
        self, user_id: int, start: date | None, end: date | None, today: date, habit_id: int | None
    ) -> HistoryRead:
        """Quota and weekly values per habit over up to a year; the days only for one habit.

        Default range: the last 12 weeks up to today. One query per table, however long the range.
        """
        end = end or today
        start = start or week_start(end) - timedelta(weeks=HISTORY_WEEKS - 1)
        if end < start:
            raise AppError(422, "range.end_before_start", "The end date is before the start date")
        if (end - start) >= timedelta(days=MAX_HISTORY_DAYS):
            raise AppError(422, "range.too_long", f"At most {MAX_HISTORY_DAYS} days at once", max_days=MAX_HISTORY_DAYS)
        if habit_id is not None:
            habit = self.repository.get_for_user(habit_id, user_id)
            if habit is None:
                raise AppError(404, "habit.not_found", "Habit not found")
            habits = [habit]
        else:
            habits = [
                h
                for h in self.repository.list_active_between(user_id, start)
                if h.schedules and h.schedules[0].valid_from <= end
            ]
        first, last = _whole_weeks(start, end)
        checkins = self.repository.checkins_between([h.id for h in habits], first, last)
        pauses = self.repository.pauses_overlapping(user_id, first, last)
        by_habit: dict[int, dict[date, Checkin]] = {}
        for checkin in checkins:
            by_habit.setdefault(checkin.habit_id, {})[checkin.local_date] = checkin

        result = []
        for habit in habits:
            entries = by_habit.get(habit.id, {})
            evaluation = evaluate_range(
                habit.schedules, _entries(entries.values()), _pauses_for(habit, pauses), start, end, today
            )
            plan = shown_plan(habit, today)
            days = None
            if habit_id is not None:
                days = [
                    HistoryDayRead(
                        date=info.date,
                        state=info.state,
                        value=info.value,
                        note=entries[info.date].note if info.date in entries else None,
                    )
                    for info in evaluation.days
                ]
            result.append(
                HistoryHabitRead(
                    id=habit.id,
                    name=habit.name,
                    archived=habit.archived_on is not None,
                    goal_type=plan.goal_type,
                    target=plan.target,
                    unit=habit.unit,
                    color=habit.color,
                    group_id=habit.group_id,
                    quota=QuotaRead(done=evaluation.quota.done, due=evaluation.quota.due),
                    weeks=[
                        HistoryWeekRead(week_start=monday, done=q.done, due=q.due) for monday, q in evaluation.weeks
                    ],
                    days=days,
                )
            )
        return HistoryRead(today=today, start=start, end=end, habits=result)


def _whole_weeks(start: date, end: date) -> tuple[date, date]:
    return week_start(start), week_start(end) + timedelta(days=6)


def _entries(checkins) -> dict[date, Entry]:
    return {c.local_date: Entry(done=c.done, value=c.value) for c in checkins}


def _pauses_for(habit: Habit, pauses: list[HabitPause]) -> list[HabitPause]:
    return [p for p in pauses if p.habit_id is None or p.habit_id == habit.id]


def _value_of(checkin: Checkin | None, target: int | None) -> int:
    """The amount of a quantity day; an old check-off without a value counts as the target."""
    if checkin is None:
        return 0
    if checkin.value is not None:
        return checkin.value
    return (target or 1) if checkin.done else 0
