from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.auth import AccountSettings


class OidcStart(BaseModel):
    purpose: Literal["login", "link", "reauth"] = "login"
    # link/reauth: where to return in the web app ("/account", "/admin" or "/")
    return_to: str | None = Field(default=None, max_length=64)
    # link: accounts with a password confirm it first
    password: str | None = Field(default=None, min_length=1, max_length=256)


class OidcRedirect(BaseModel):
    """Send the browser here (window.location), it comes back through the callback."""

    authorize_url: str


class InvitationOidcStart(AccountSettings):
    token: str = Field(min_length=1, max_length=200)
    # signup links only
    username: str | None = Field(default=None, max_length=80)


class SetupOidcStart(AccountSettings):
    token: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=80)


class OidcUnlink(BaseModel):
    password: str | None = Field(default=None, min_length=1, max_length=256)
