from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.auth import RoleLiteral


class AdminUserRead(BaseModel):
    """What an admin sees about an account: no habits, no check-ins, no counts."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str | None
    role: RoleLiteral
    is_active: bool
    created_at: datetime
    last_seen_at: datetime | None


class AdminUserUpdate(BaseModel):
    role: RoleLiteral | None = None
    is_active: bool | None = None
