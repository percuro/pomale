from datetime import datetime
from typing import Any

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


class AuditEventRead(BaseModel):
    id: int
    created_at: datetime
    event: str
    actor_user_id: int | None
    actor_username: str | None
    target_user_id: int | None
    target_username: str | None
    ip_prefix: str | None
    details: dict[str, Any]


class AuditPage(BaseModel):
    events: list[AuditEventRead]
    # Pass as before_id for the next (older) page; null = no more entries
    next_before_id: int | None
