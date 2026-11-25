from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.auth import AccountSettings, RoleLiteral

PurposeLiteral = Literal["signup", "password_reset"]


class InvitationCreate(BaseModel):
    role: RoleLiteral = "user"
    # e.g. "for Anna", so the admin can tell open invitations apart
    note: str | None = Field(default=None, max_length=80)

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class InvitationCreated(BaseModel):
    id: int
    purpose: PurposeLiteral
    # Shown only now; the token is only stored as a hash
    url: str
    expires_at: datetime


class InvitationRead(BaseModel):
    id: int
    purpose: PurposeLiteral
    role: RoleLiteral | None
    note: str | None
    # password_reset: the account whose password is set
    target_username: str | None
    created_by_username: str | None
    created_at: datetime
    expires_at: datetime


class InvitationToken(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class InvitationInfo(BaseModel):
    purpose: PurposeLiteral
    # password_reset: the account; signup: null
    username: str | None
    expires_at: datetime


class InvitationAccept(AccountSettings):
    token: str = Field(min_length=1, max_length=200)
    # signup only
    username: str | None = Field(default=None, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(AccountSettings):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class OidcMeta(BaseModel):
    # Name for the button; null = the web app's translated default
    label: str | None


class MetaRead(BaseModel):
    version: str
    registration: Literal["invite", "open"]
    setup_needed: bool
    # False: sign-in, registration and setup through OIDC only
    password_login: bool
    # null = OIDC not configured
    oidc: OidcMeta | None
