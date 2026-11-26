"""The JSON export (format "pomale-export", version 1): one account's habits, check-ins and settings.

Stable from 1.0 on: new fields may be added, nothing is renamed or removed within a version. The
same model validates an import, so everything an export can contain is also checked on the way in.
References between objects use `ref` numbers that are only valid inside one file.
"""

from datetime import date, datetime, time
from typing import Literal, Self

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from app.models.habit import HABIT_COLORS, QUANTITY_TARGET_MAX, REMINDERS_MAX
from app.models.user import DAY_END_HOUR_MAX
from app.schemas.habit import GoalTypeLiteral, check_goal, check_reminders

EXPORT_FORMAT = "pomale-export"
EXPORT_VERSION = 1
# Generous limits for one person's data; they keep a broken or hostile file from exhausting memory
MAX_HABITS = 1000
MAX_CHECKINS_PER_HABIT = 20000
MAX_SCHEDULES_PER_HABIT = 500
MAX_GROUPS = 200
MAX_PAUSES = 2000


def _strip(value: str | None) -> str | None:
    return value.strip() or None if value is not None else None


class ExportAccount(BaseModel):
    # null: the server's default time zone / the browser's language
    timezone: str | None = Field(default=None, max_length=64)
    locale: Literal["de", "en"] | None = None
    day_end_hour: int = Field(default=0, ge=0, le=DAY_END_HOUR_MAX)


class ExportGroup(BaseModel):
    ref: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=60)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value


class ExportSchedule(BaseModel):
    valid_from: date
    # Bit 0 = Monday … bit 6 = Sunday; 0 = not planned
    weekdays: int = Field(ge=0, le=127)
    goal_type: GoalTypeLiteral = "days"
    target: int | None = None

    @model_validator(mode="after")
    def valid_goal(self) -> Self:
        check_goal(self.goal_type, self.target)
        return self


class ExportCheckin(BaseModel):
    date: date
    done: bool
    # quantity goals only
    value: int | None = Field(default=None, ge=0, le=QUANTITY_TARGET_MAX)
    note: str | None = Field(default=None, max_length=500)

    _strip_note = field_validator("note")(classmethod(lambda cls, value: _strip(value)))


class ExportHabit(BaseModel):
    ref: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    cue: str | None = Field(default=None, max_length=200)
    sort_order: int = Field(default=0, ge=0)
    archived_on: date | None = None
    unit: str | None = Field(default=None, max_length=20)
    color: str | None = None
    group_ref: int | None = None
    created_at: datetime | None = None
    schedules: list[ExportSchedule] = Field(min_length=1, max_length=MAX_SCHEDULES_PER_HABIT)
    reminders: list[time] = Field(default_factory=list, max_length=REMINDERS_MAX)
    checkins: list[ExportCheckin] = Field(default_factory=list, max_length=MAX_CHECKINS_PER_HABIT)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be empty")
        return value

    @field_validator("cue", "unit")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return _strip(value)

    @field_validator("color")
    @classmethod
    def known_color(cls, value: str | None) -> str | None:
        if value is not None and value not in HABIT_COLORS:
            raise ValueError(f"Colour must be one of {', '.join(HABIT_COLORS)}")
        return value

    @field_validator("reminders")
    @classmethod
    def valid_reminders(cls, value: list[time]) -> list[time]:
        return check_reminders(value) or []

    @field_serializer("reminders")
    def reminders_as_text(self, value: list[time]) -> list[str]:
        # "07:30", as everywhere else in the API
        return [item.strftime("%H:%M") for item in value]

    @model_validator(mode="after")
    def unique_days(self) -> Self:
        if len({s.valid_from for s in self.schedules}) != len(self.schedules):
            raise ValueError("Two plans of a habit start on the same day")
        if len({c.date for c in self.checkins}) != len(self.checkins):
            raise ValueError("A habit has two entries for the same day")
        return self


class ExportPause(BaseModel):
    # null: all habits
    habit_ref: int | None = None
    start_on: date
    end_on: date
    reason: str | None = Field(default=None, max_length=80)

    _strip_reason = field_validator("reason")(classmethod(lambda cls, value: _strip(value)))

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.end_on < self.start_on:
            raise ValueError("A pause ends before it starts")
        return self


class AccountExport(BaseModel):
    format: Literal["pomale-export"] = EXPORT_FORMAT
    version: Literal[1] = EXPORT_VERSION
    app_version: str | None = Field(default=None, max_length=40)
    exported_at: datetime | None = None
    account: ExportAccount = Field(default_factory=ExportAccount)
    groups: list[ExportGroup] = Field(default_factory=list, max_length=MAX_GROUPS)
    habits: list[ExportHabit] = Field(default_factory=list, max_length=MAX_HABITS)
    pauses: list[ExportPause] = Field(default_factory=list, max_length=MAX_PAUSES)

    @model_validator(mode="after")
    def references(self) -> Self:
        group_refs = [g.ref for g in self.groups]
        habit_refs = [h.ref for h in self.habits]
        if len(set(group_refs)) != len(group_refs) or len(set(habit_refs)) != len(habit_refs):
            raise ValueError("Every ref must be unique within groups and within habits")
        if len({g.name for g in self.groups}) != len(self.groups):
            raise ValueError("Two groups have the same name")
        for habit in self.habits:
            if habit.group_ref is not None and habit.group_ref not in group_refs:
                raise ValueError(f"Habit {habit.ref} refers to a group that is not in the file")
        for pause in self.pauses:
            if pause.habit_ref is not None and pause.habit_ref not in habit_refs:
                raise ValueError("A pause refers to a habit that is not in the file")
        return self


class ImportResult(BaseModel):
    groups: int
    habits: int
    checkins: int
    pauses: int
    reminders: int
    # Settings taken over from the file; a time zone this server does not know is left out
    settings: list[str]
