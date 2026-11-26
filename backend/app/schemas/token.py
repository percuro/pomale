from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ScopeLiteral = Literal["read", "checkin"]


class TokenCreate(BaseModel):
    label: str = Field(default="API", min_length=1, max_length=80)
    scopes: list[ScopeLiteral] = Field(min_length=1, max_length=2, description="read: see; checkin: check off")
    # Empty: all habits, also those created later
    habit_ids: list[int] = Field(default_factory=list, max_length=200)
    # None: the key does not expire
    expires_in_days: Literal[30, 90, 365] | None = None


class TokenRead(BaseModel):
    id: int
    label: str
    scopes: list[ScopeLiteral]
    # Empty: all habits
    habit_ids: list[int]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class TokenCreated(TokenRead):
    token: str = Field(description="Shown only now; only its hash is stored")
