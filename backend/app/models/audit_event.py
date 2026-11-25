from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AuditEvent(Base):
    """Security-relevant event for admins. Usernames are copied so entries stay readable after deletion."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    event: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Shortened (IPv4 /24, IPv6 /48), and only for failed logins and rate-limit blocks
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Small JSON object; never passwords or tokens
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
