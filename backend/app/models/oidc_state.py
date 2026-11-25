from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

PURPOSE_LOGIN = "login"
PURPOSE_LINK = "link"
PURPOSE_REAUTH = "reauth"
PURPOSE_SIGNUP = "signup"
PURPOSE_SETUP = "setup"
PURPOSE_RECOVER = "recover"
PURPOSES = (PURPOSE_LOGIN, PURPOSE_LINK, PURPOSE_REAUTH, PURPOSE_SIGNUP, PURPOSE_SETUP, PURPOSE_RECOVER)


class OidcLoginState(Base):
    """One started sign-in at the provider, valid for a few minutes and used once.

    Kept in the database rather than a signed cookie: pomale has no secret key to sign with.
    The browser holds the raw state in a cookie; only its SHA-256 hash is stored here.
    """

    __tablename__ = "oidc_login_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    # link and reauth: the signed-in account
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    # link and reauth: the session that started it
    session_id: Mapped[int | None] = mapped_column(ForeignKey("user_sessions.id", ondelete="CASCADE"), nullable=True)
    # signup and recover: the one-time link
    invitation_id: Mapped[int | None] = mapped_column(ForeignKey("invitations.id", ondelete="CASCADE"), nullable=True)
    # signup and setup: chosen username and settings as JSON
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
