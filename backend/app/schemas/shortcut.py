from datetime import date, datetime
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
    done: bool = True
    # Quantity goals: how much to add (default 1)
    amount: int | None = Field(default=None, ge=1, le=1000)


class ShortcutCheckinRead(BaseModel):
    habit_id: int
    habit_name: str
    date: date
    done: bool
    # Stable for automations: "done" (checked off now), "already_done",
    # or "counted" (quantity goals: amount added, see value and target)
    result: Literal["done", "already_done", "counted"]
    # quantity goals only
    value: int | None = None
    target: int | None = None
    # Human-readable, in the owner's language (else the phone's, else English)
    status: str
    message: str
