from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.habit import Habit
from app.models.user import User

SCOPE_READ = "read"
SCOPE_CHECKIN = "checkin"
SCOPES = (SCOPE_READ, SCOPE_CHECKIN)

# Which habits a token may see and check off; no rows = all habits of its owner
api_token_habits = Table(
    "api_token_habits",
    Base.metadata,
    Column("token_id", ForeignKey("api_tokens.id", ondelete="CASCADE"), primary_key=True),
    Column("habit_id", ForeignKey("habits.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class ApiToken(Base):
    """Personal API key: reads and/or checks off for its owner, never more (see token_service).

    The iOS shortcut keys of 0.3–0.9 became tokens with scope "checkin" for exactly one habit.
    """

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # Comma-separated, e.g. "read,checkin"
    scopes: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # None = does not expire
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()
    habits: Mapped[list[Habit]] = relationship(secondary=api_token_habits, order_by=Habit.id)

    @property
    def scope_set(self) -> frozenset[str]:
        return frozenset(scope for scope in self.scopes.split(",") if scope)

    @property
    def habit_ids(self) -> list[int]:
        return [habit.id for habit in self.habits]
