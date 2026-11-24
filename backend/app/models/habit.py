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


class Habit(Base):
    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    cue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    schedules: Mapped[list["HabitSchedule"]] = relationship(
        back_populates="habit",
        cascade="all, delete-orphan",
        order_by="HabitSchedule.valid_from",
    )
    checkins: Mapped[list["Checkin"]] = relationship(back_populates="habit", cascade="all, delete-orphan")


class HabitSchedule(Base):
    """Plan from an effective date. Bit 0 = Monday … bit 6 = Sunday; 0 = not planned."""

    __tablename__ = "habit_schedules"
    __table_args__ = (
        UniqueConstraint("habit_id", "valid_from", name="uq_habit_schedule_valid_from"),
        CheckConstraint("weekdays BETWEEN 0 AND 127", name="ck_habit_schedule_weekdays"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    weekdays: Mapped[int] = mapped_column(Integer, nullable=False)

    habit: Mapped[Habit] = relationship(back_populates="schedules")


class Checkin(Base):
    __tablename__ = "checkins"

    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_op_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    habit: Mapped[Habit] = relationship(back_populates="checkins")
