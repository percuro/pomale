import datetime as _dt
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShortcutTokenCreate(BaseModel):
    label: str = Field(default="iPhone", min_length=1, max_length=80)


class ShortcutTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ShortcutTokenCreated(ShortcutTokenRead):
    token: str = Field(description="Shown only now; only its hash is stored")


class ShortcutCheckinRequest(BaseModel):
    done: bool = Field(default=True, description="Only true: this endpoint does not undo (`shortcut.done_only`)")
    amount: int | None = Field(default=None, ge=1, le=1000, description="Quantity goals: how much to add (default 1)")


class ShortcutCheckinRead(BaseModel):
    habit_id: int
    habit_name: str
    date: _dt.date = Field(description="The day that was checked off: the owner's today, with time zone and day end")
    done: bool
    result: Literal["done", "already_done", "counted"] = Field(
        description="For automations, the same in every language: `done` (checked off now), `already_done`, "
        "or `counted` (quantity goals: amount added, see `value` and `target`)"
    )
    value: int | None = Field(default=None, description="Quantity goals only")
    target: int | None = Field(default=None, description="Quantity goals only")
    status: str = Field(description="Human-readable result in the owner's language (else the phone's, else English)")
    message: str = Field(description="`<habit name>: <status>`, ready to show as a notification")
