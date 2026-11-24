from datetime import date, datetime

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
    status: str
    message: str
