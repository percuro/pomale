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


class ShortcutCheckinRead(BaseModel):
    habit_id: int
    habit_name: str
    date: date
    done: bool
    # Stable for automations: "done" (checked off now) or "already_done"
    result: Literal["done", "already_done"]
    # Human-readable, in the owner's language (else the phone's, else English)
    status: str
    message: str
