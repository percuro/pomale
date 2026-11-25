from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.user import User

SUBSCRIPTIONS_MAX = 20


class InstanceSecret(Base):
    """Instance-wide keys that are generated once, e.g. the VAPID key for Web Push."""

    __tablename__ = "instance_secrets"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class PushSubscription(Base):
    """One device (browser profile) that receives reminders.

    Bound to the session that created it: logging out there removes it, so a shared device stops
    showing habit names. When a session merely expires, session_id becomes NULL and it stays.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(100), nullable=False)
    auth: Mapped[str] = mapped_column(String(40), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user: Mapped[User] = relationship()
