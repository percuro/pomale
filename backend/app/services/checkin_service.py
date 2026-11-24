from datetime import date, timedelta

from fastapi import HTTPException, status

from app.models.habit import Checkin, Habit
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import CheckinRead, DayRead, DaysRead, HabitDaysRead, QuotaRead
from app.services.day_service import build_days, day_state, is_planned, quota

MAX_RANGE_DAYS = 62


class CheckinService:
    def __init__(self, repository: HabitRepository):
        self.repository = repository

    def set_state(
        self,
        habit: Habit,
        day: date,
        done: bool,
        today: date,
        op_id: str | None = None,
        base_version: int | None = None,
    ) -> CheckinRead:
        """Set the state (never toggle). Repeating a request creates no second entry.

        With base_version (offline queue): if the target state is already there, that
        counts as success. If the entry changed since base_version, answer 409 with the
        server state instead of silently overwriting it.
        """
        if day > today:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Zukünftige Tage können nicht erfasst werden",
            )
        checkin = self.repository.get_checkin(habit.id, day)
        current_done = bool(checkin and checkin.done)
        current_version = checkin.version if checkin else 0
        if current_done == done:
            return self._read(habit, day, checkin, today)
        if base_version is not None and base_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Der Eintrag wurde inzwischen auf einem anderen Gerät geändert",
                    "server": self._read(habit, day, checkin, today).model_dump(mode="json")
                    | {"updated_at": checkin.updated_at.isoformat() + "Z" if checkin else None},
                },
            )
        if checkin is None:
            # Concurrent creation (double tap): one insert wins, the other reads its entry
            inserted = self.repository.insert_checkin(
                Checkin(habit_id=habit.id, local_date=day, done=True, version=1, last_op_id=op_id)
            )
            checkin = self.repository.get_checkin(habit.id, day)
            if not inserted and checkin is not None and checkin.done != done:
                return self.set_state(habit, day, done, today, op_id, base_version)
        else:
            checkin.done = done
            checkin.version += 1
            checkin.last_op_id = op_id
            self.repository.commit()
        return self._read(habit, day, checkin, today)

    def _read(self, habit: Habit, day: date, checkin: Checkin | None, today: date) -> CheckinRead:
        done = bool(checkin and checkin.done)
        planned = is_planned(habit.schedules, day)
        return CheckinRead(
            habit_id=habit.id,
            date=day,
            done=done,
            state=day_state(planned, done, day, today),
            version=checkin.version if checkin else 0,
        )

    def days(self, user_id: int, start: date, end: date, today: date, timezone: str) -> DaysRead:
        if end < start:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Ende liegt vor Beginn")
        if (end - start) > timedelta(days=MAX_RANGE_DAYS):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Höchstens {MAX_RANGE_DAYS} Tage auf einmal",
            )
        habits = self.repository.list_active_between(user_id, start)
        checkins = self.repository.checkins_between([h.id for h in habits], start, end)
        by_habit: dict[int, dict[date, Checkin]] = {}
        for checkin in checkins:
            by_habit.setdefault(checkin.habit_id, {})[checkin.local_date] = checkin

        result = []
        for habit in habits:
            entries = by_habit.get(habit.id, {})
            done_dates = {d for d, c in entries.items() if c.done}
            infos = build_days(habit.schedules, done_dates, start, end, today)
            q = quota(infos, today)
            result.append(
                HabitDaysRead(
                    id=habit.id,
                    name=habit.name,
                    cue=habit.cue,
                    archived=habit.archived_on is not None,
                    days=[
                        DayRead(
                            date=info.date,
                            state=info.state,
                            planned=info.planned,
                            done=info.done,
                            version=entries[info.date].version if info.date in entries else 0,
                        )
                        for info in infos
                    ],
                    quota=QuotaRead(done=q.done, due=q.due),
                )
            )
        return DaysRead(today=today, timezone=timezone, start=start, end=end, habits=result)
