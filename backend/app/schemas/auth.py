from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.user import DAY_END_HOUR_MAX
from app.services.timezones import is_known_timezone

LocaleLiteral = Literal["de", "en"]
RoleLiteral = Literal["admin", "user"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class AccountSettings(BaseModel):
    """Optional per-account settings; null means "not set" (server default / browser language)."""

    display_name: str | None = Field(default=None, max_length=80)
    timezone: str | None = Field(default=None, max_length=64)
    locale: LocaleLiteral | None = None

    @field_validator("display_name")
    @classmethod
    def strip_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not is_known_timezone(value):
            raise ValueError("Unknown time zone")
        return value


class AccountUpdate(AccountSettings):
    """PATCH: only the fields sent are changed."""

    # The full hour at which the day ends (0 = midnight); not part of sign-up, always has a value
    day_end_hour: int = Field(default=0, ge=0, le=DAY_END_HOUR_MAX)


class OidcLinkRead(BaseModel):
    """What the provider told us when the account last signed in; for display only."""

    email: str | None
    preferred_username: str | None
    linked_at: datetime


class MeRead(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: RoleLiteral
    # Effective time zone ("today" is computed in it) and the account's own setting (null = server default)
    timezone: str
    timezone_setting: str | None
    # The server's DEFAULT_TIMEZONE, used while timezone_setting is null
    default_timezone: str
    locale: LocaleLiteral | None
    # The day ends at this full hour (0 = midnight); "today" already takes it into account
    day_end_hour: int
    today: date
    # False: the account signs in through OIDC only
    has_password: bool
    oidc: OidcLinkRead | None


class PasswordChange(BaseModel):
    # Not needed by accounts without a password; they confirm with a fresh OIDC login instead
    current_password: str | None = Field(default=None, min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class PasswordConfirmation(BaseModel):
    # Not needed by accounts without a password (see PasswordChange)
    password: str | None = Field(default=None, min_length=1, max_length=256)


class SessionRead(BaseModel):
    id: int
    created_at: datetime
    last_seen_at: datetime | None
    # e.g. "iPhone · Safari"; null when the browser is not recognised
    device: str | None
    current: bool
