from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.user import User

PURPOSE_SIGNUP = "signup"
PURPOSE_PASSWORD_RESET = "password_reset"


class Invitation(Base):
    """One-time link: either to create an account or to set a new password.

    Only the SHA-256 hash of the token is stored; the link is shown once.
    """

    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    # signup: role of the new account
    role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # password_reset: the account whose password is set
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    target_user: Mapped[User | None] = relationship(foreign_keys=[target_user_id])
