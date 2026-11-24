from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _NameMixin(BaseModel):
    @field_validator("name", check_fields=False)
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name darf nicht leer sein")
        return value

    @field_validator("cue", check_fields=False)
    @classmethod
    def strip_cue(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip() or None


class HabitCreate(_NameMixin):
    name: str = Field(max_length=120)
    cue: str | None = Field(default=None, max_length=200)
    weekdays: int = Field(default=127, ge=1, le=127)
    start_on: date | None = None


class HabitUpdate(_NameMixin):
    name: str | None = Field(default=None, max_length=120)
    cue: str | None = Field(default=None, max_length=200)
    sort_order: int | None = None


class ScheduleUpdate(BaseModel):
    weekdays: int = Field(ge=1, le=127)
    valid_from: date | None = None


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    valid_from: date
    weekdays: int


class HabitRead(BaseModel):
    id: int
    name: str
    cue: str | None
    sort_order: int
    archived_on: date | None
    weekdays: int
    schedules: list[ScheduleRead]


DayStateLiteral = Literal["not_planned", "open", "done", "extra_done", "future"]


class DayRead(BaseModel):
    date: date
    state: DayStateLiteral
    planned: bool
    done: bool
    version: int


class QuotaRead(BaseModel):
    done: int
    due: int


class HabitDaysRead(BaseModel):
    id: int
    name: str
    cue: str | None
    archived: bool
    days: list[DayRead]
    quota: QuotaRead


class DaysRead(BaseModel):
    today: date
    timezone: str
    start: date
    end: date
    habits: list[HabitDaysRead]


class CheckinUpdate(BaseModel):
    done: bool
    # Offline queue: unique operation id and the last version the client saw
    op_id: str | None = Field(default=None, max_length=64)
    base_version: int | None = Field(default=None, ge=0)


class CheckinRead(BaseModel):
    habit_id: int
    date: date
    done: bool
    state: DayStateLiteral
    version: int
