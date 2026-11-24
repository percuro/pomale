from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_today
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import HabitCreate, HabitRead, HabitUpdate, ScheduleUpdate
from app.services.habit_service import HabitService, habit_read

router = APIRouter()


def _service(db: Session) -> HabitService:
    return HabitService(HabitRepository(db))


@router.get("", response_model=list[HabitRead])
def list_habits(
    include_archived: bool = False,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return [habit_read(h, today) for h in _service(db).list(user.id, include_archived)]


@router.post("", response_model=HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(
    data: HabitCreate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return habit_read(_service(db).create(user.id, data, today), today)


@router.patch("/{habit_id}", response_model=HabitRead)
def update_habit(
    habit_id: int,
    data: HabitUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return habit_read(_service(db).update(habit_id, user.id, data), today)


@router.put("/{habit_id}/schedule", response_model=HabitRead)
def set_schedule(
    habit_id: int,
    data: ScheduleUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return habit_read(_service(db).set_schedule(habit_id, user.id, data, today), today)


@router.post("/{habit_id}/archive", response_model=HabitRead)
def archive_habit(
    habit_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return habit_read(_service(db).archive(habit_id, user.id, today), today)


@router.post("/{habit_id}/unarchive", response_model=HabitRead)
def unarchive_habit(
    habit_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    return habit_read(_service(db).unarchive(habit_id, user.id, today), today)
