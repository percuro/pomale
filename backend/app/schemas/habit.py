from datetime import date, time
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.habit import HABIT_COLORS, QUANTITY_TARGET_MAX, REMINDERS_MAX, WEEKLY_TARGET_MAX

GoalTypeLiteral = Literal["days", "weekly_count", "quantity"]


def check_goal(goal_type: str | None, target: int | None) -> None:
    """Raise ValueError unless the target fits the goal type (None = keep the current type)."""
    if goal_type == "days" and target is not None:
        raise ValueError("A days goal has no target")
    if goal_type == "weekly_count" and (target is None or not 1 <= target <= WEEKLY_TARGET_MAX):
        raise ValueError(f"A weekly goal needs a target from 1 to {WEEKLY_TARGET_MAX}")
    if goal_type == "quantity" and (target is None or not 1 <= target <= QUANTITY_TARGET_MAX):
        raise ValueError(f"A quantity goal needs a target from 1 to {QUANTITY_TARGET_MAX}")


class _NameMixin(BaseModel):
    @field_validator("name", check_fields=False)
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value

    @field_validator("cue", "unit", check_fields=False)
    @classmethod
    def strip_cue(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip() or None

    @field_validator("color", check_fields=False)
    @classmethod
    def known_color(cls, value: str | None) -> str | None:
        if value is not None and value not in HABIT_COLORS:
            raise ValueError(f"Colour must be one of {', '.join(HABIT_COLORS)}")
        return value


def check_reminders(value: list[time] | None) -> list[time] | None:
    """Whole minutes, no time zone (the account's applies), no duplicates; returned sorted."""
    if value is None:
        return value
    for item in value:
        if item.second or item.microsecond or item.tzinfo is not None:
            raise ValueError("Reminder times are local times in whole minutes, e.g. 07:30")
    if len(set(value)) != len(value):
        raise ValueError("Reminder times must not repeat")
    return sorted(value)


class _RemindersMixin(BaseModel):
    @field_validator("reminders", check_fields=False)
    @classmethod
    def valid_reminders(cls, value: list[time] | None) -> list[time] | None:
        return check_reminders(value)


class HabitCreate(_NameMixin, _RemindersMixin):
    name: str = Field(max_length=120)
    cue: str | None = Field(default=None, max_length=200)
    weekdays: int = Field(default=127, ge=1, le=127)
    start_on: date | None = None
    goal_type: GoalTypeLiteral = "days"
    target: int | None = None
    unit: str | None = Field(default=None, max_length=20)
    color: str | None = None
    group_id: int | None = None
    reminders: list[time] = Field(default_factory=list, max_length=REMINDERS_MAX)

    @model_validator(mode="after")
    def goal_fits(self) -> Self:
        check_goal(self.goal_type, self.target)
        if self.goal_type == "weekly_count":
            # any day counts toward a weekly goal
            self.weekdays = 127
        return self


class HabitUpdate(_NameMixin, _RemindersMixin):
    name: str | None = Field(default=None, max_length=120)
    cue: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None
    unit: str | None = Field(default=None, max_length=20)
    color: str | None = None
    group_id: int | None = None
    # Replaces all reminder times; [] removes them
    reminders: list[time] | None = Field(default=None, max_length=REMINDERS_MAX)


class ScheduleUpdate(BaseModel):
    """A new plan from valid_from (default today). Without goal_type the current type and target stay."""

    weekdays: int = Field(default=127, ge=1, le=127)
    valid_from: date | None = None
    goal_type: GoalTypeLiteral | None = None
    target: int | None = None

    @model_validator(mode="after")
    def goal_fits(self) -> Self:
        if self.goal_type is not None:
            check_goal(self.goal_type, self.target)
        if self.goal_type == "weekly_count":
            self.weekdays = 127
        return self


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid_from: date
    weekdays: int
    goal_type: GoalTypeLiteral
    target: int | None


class HabitRead(BaseModel):
    id: int
    name: str
    cue: str | None
    sort_order: int
    archived_on: date | None
    # the plan in effect today (or the last one, for archived and future habits)
    weekdays: int
    goal_type: GoalTypeLiteral
    target: int | None
    unit: str | None
    color: str | None
    group_id: int | None
    # Local times "HH:MM" in the account's time zone, sorted
    reminders: list[str]
    schedules: list[ScheduleRead]


class HabitOrderItem(BaseModel):
    id: int
    group_id: int | None = None


class HabitOrder(BaseModel):
    """The habits in their new order; habits not listed keep their order after them."""

    habits: list[HabitOrderItem] = Field(max_length=1000)


class GroupCreate(BaseModel):
    name: str = Field(max_length=60)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value


class GroupUpdate(GroupCreate):
    pass


class GroupOrder(BaseModel):
    ids: list[int] = Field(max_length=1000)


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int


class PauseCreate(BaseModel):
    """habit_id null = all habits of the account. Both days count (inclusive)."""

    habit_id: int | None = None
    start_on: date
    end_on: date
    reason: str | None = Field(default=None, max_length=80)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PauseUpdate(BaseModel):
    habit_id: int | None = None
    start_on: date | None = None
    end_on: date | None = None
    reason: str | None = Field(default=None, max_length=80)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PauseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    habit_id: int | None
    start_on: date
    end_on: date
    reason: str | None


DayStateLiteral = Literal["not_planned", "open", "done", "extra_done", "future", "paused", "partial"]


class DayRead(BaseModel):
    """One day of one habit. goal_type, target, planned, paused, done and value are the raw
    input of the evaluation (day_service.evaluate), so clients can re-evaluate offline changes."""

    date: date
    state: DayStateLiteral
    planned: bool
    # days and weekly goals: checked off; quantity goals: target reached
    done: bool
    version: int
    goal_type: GoalTypeLiteral
    # quantity: per day; weekly goal: this week's target, reduced for pauses
    target: int | None
    paused: bool
    # quantity goals only
    value: int | None
    note: str | None


class QuotaRead(BaseModel):
    done: int
    due: int


class WeekRead(BaseModel):
    done: int
    target: int


class HabitDaysRead(BaseModel):
    id: int
    name: str
    cue: str | None
    archived: bool
    # the plan in effect today
    goal_type: GoalTypeLiteral
    target: int | None
    unit: str | None
    color: str | None
    group_id: int | None
    days: list[DayRead]
    quota: QuotaRead
    # weekly goals: progress in the week that contains today
    week: WeekRead | None


class DaysRead(BaseModel):
    today: date
    timezone: str
    start: date
    end: date
    groups: list[GroupRead]
    habits: list[HabitDaysRead]


class CheckinUpdate(BaseModel):
    """Set the state of a day: `done`, or `value` for quantity goals (never both).

    `done` on a quantity goal sets the value to the target (true) or 0 (false).
    """

    done: bool | None = None
    value: int | None = Field(default=None, ge=0, le=QUANTITY_TARGET_MAX)
    # Offline queue: unique operation id and the last version the client saw
    op_id: str | None = Field(default=None, max_length=64)
    base_version: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def one_of(self) -> Self:
        if (self.done is None) == (self.value is None):
            raise ValueError("Send either done or value")
        return self


class CheckinRead(BaseModel):
    habit_id: int
    date: date
    done: bool
    state: DayStateLiteral
    version: int
    value: int | None


class NoteUpdate(BaseModel):
    # empty or null removes the note
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class NoteRead(BaseModel):
    habit_id: int
    date: date
    note: str | None


class HistoryWeekRead(BaseModel):
    week_start: date
    done: int
    due: int


class HistoryDayRead(BaseModel):
    date: date
    state: DayStateLiteral
    value: int | None
    note: str | None


class HistoryHabitRead(BaseModel):
    id: int
    name: str
    archived: bool
    goal_type: GoalTypeLiteral
    target: int | None
    unit: str | None
    color: str | None
    group_id: int | None
    quota: QuotaRead
    weeks: list[HistoryWeekRead]
    # only when asking for one habit
    days: list[HistoryDayRead] | None


class HistoryRead(BaseModel):
    today: date
    start: date
    end: date
    habits: list[HistoryHabitRead]


class TodayHabitRead(BaseModel):
    id: int
    name: str
    cue: str | None
    goal_type: GoalTypeLiteral
    state: DayStateLiteral
    # quantity goals: today's amount and target; weekly goals: this week's target
    value: int | None
    target: int | None
    unit: str | None
    week: WeekRead | None
    # "3 of 8 glasses", "1 of 3 this week"; null for goals on chosen days
    progress: str | None


class TodayRead(BaseModel):
    """What is still open today, for shortcuts, widgets and home automation."""

    date: date
    # habits due today, and how many of them are done
    due: int
    done: int
    open: list[TodayHabitRead]
    # One sentence in the account's language, e.g. "Still open: Read, Water (3 of 8 glasses)"
    message: str
