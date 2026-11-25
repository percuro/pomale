from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_user_today
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import CheckinRead, CheckinUpdate, DaysRead, NoteRead, NoteUpdate
from app.services.checkin_service import CheckinService
from app.services.day_service import week_start
from app.services.habit_service import HabitService
from app.services.timezones import effective_timezone_name

router = APIRouter()


@router.get("/days", response_model=DaysRead)
def list_days(
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    start = start or week_start(today)
    end = end or start + timedelta(days=6)
    return CheckinService(HabitRepository(db)).days(user.id, start, end, today, effective_timezone_name(user))


@router.put("/habits/{habit_id}/days/{day}", response_model=CheckinRead)
def set_day(
    habit_id: int,
    day: date,
    data: CheckinUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    repository = HabitRepository(db)
    habit = HabitService(repository).get(habit_id, user.id)
    return CheckinService(repository).set_state(
        habit, day, today, done=data.done, value=data.value, op_id=data.op_id, base_version=data.base_version
    )


@router.put("/habits/{habit_id}/days/{day}/note", response_model=NoteRead)
def set_note(
    habit_id: int,
    day: date,
    data: NoteUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    repository = HabitRepository(db)
    habit = HabitService(repository).get(habit_id, user.id)
    return CheckinService(repository).set_note(habit, day, data.note, today)
