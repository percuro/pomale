from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.user import User

GOAL_TYPES = ("days", "weekly_count", "quantity")
WEEKLY_TARGET_MAX = 7
QUANTITY_TARGET_MAX = 9999
# Keys of the fixed palette; the frontend maps them to colours that pass contrast checks
HABIT_COLORS = ("slate", "red", "orange", "amber", "green", "teal", "blue", "purple", "pink")


class HabitGroup(Base):
    """Named section on the today and week views, per account."""

    __tablename__ = "habit_groups"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_habit_groups_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    cue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("habit_groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    user: Mapped[User] = relationship()
    group: Mapped[HabitGroup | None] = relationship()
    schedules: Mapped[list["HabitSchedule"]] = relationship(
        back_populates="habit",
        cascade="all, delete-orphan",
        order_by="HabitSchedule.valid_from",
    )
    checkins: Mapped[list["Checkin"]] = relationship(back_populates="habit", cascade="all, delete-orphan")


class HabitSchedule(Base):
    """Plan from an effective date. Bit 0 = Monday … bit 6 = Sunday; 0 = not planned.

    goal_type "days": check off on the planned weekdays (target is NULL).
    goal_type "weekly_count": target check-ins per week on any day (weekdays 127, or 0).
    goal_type "quantity": reach target per planned day, e.g. 8 glasses.
    """

    __tablename__ = "habit_schedules"
    __table_args__ = (
        UniqueConstraint("habit_id", "valid_from", name="uq_habit_schedule_valid_from"),
        CheckConstraint("weekdays BETWEEN 0 AND 127", name="ck_habit_schedule_weekdays"),
        CheckConstraint(
            "(goal_type = 'days' AND target IS NULL)"
            f" OR (goal_type = 'weekly_count' AND target IS NOT NULL AND target BETWEEN 1 AND {WEEKLY_TARGET_MAX})"
            f" OR (goal_type = 'quantity' AND target IS NOT NULL AND target BETWEEN 1 AND {QUANTITY_TARGET_MAX})",
            name="ck_habit_schedule_goal",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    weekdays: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_type: Mapped[str] = mapped_column(String(16), nullable=False, default="days", server_default="days")
    target: Mapped[int | None] = mapped_column(Integer, nullable=True)

    habit: Mapped[Habit] = relationship(back_populates="schedules")


class Checkin(Base):
    """One habit on one day. For quantity habits `value` is the truth and `done` mirrors value > 0;
    whether the target is reached is computed when reading. `note` never changes `version`."""

    __tablename__ = "checkins"
    __table_args__ = (
        CheckConstraint(f"value IS NULL OR value BETWEEN 0 AND {QUANTITY_TARGET_MAX}", name="ck_checkins_value"),
    )

    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False)
    value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_op_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    habit: Mapped[Habit] = relationship(back_populates="checkins")


class HabitPause(Base):
    """Days (inclusive) that are not due: holidays, illness. habit_id NULL = all habits of the account."""

    __tablename__ = "habit_pauses"
    __table_args__ = (CheckConstraint("end_on >= start_on", name="ck_habit_pauses_range"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    habit_id: Mapped[int | None] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), nullable=True, index=True)
    start_on: Mapped[date] = mapped_column(Date, nullable=False)
    end_on: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
