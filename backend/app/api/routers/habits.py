from datetime import date

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_user_today
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import HabitCreate, HabitOrder, HabitRead, HabitUpdate, ScheduleUpdate
from app.services.habit_service import HabitService, habit_read
from app.services.token_service import allowed_habit_ids

router = APIRouter()


def _service(db: Session) -> HabitService:
    return HabitService(HabitRepository(db))


@router.get("", response_model=list[HabitRead])
def list_habits(
    request: Request,
    include_archived: bool = False,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    allowed = allowed_habit_ids(request)
    habits = _service(db).list(user.id, include_archived)
    return [habit_read(h, today) for h in habits if allowed is None or h.id in allowed]


@router.post("", response_model=HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(
    data: HabitCreate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return habit_read(_service(db).create(user.id, data, today), today)


@router.put("/order", response_model=list[HabitRead])
def reorder_habits(
    data: HabitOrder,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return [habit_read(h, today) for h in _service(db).reorder(user.id, data)]


@router.patch("/{habit_id}", response_model=HabitRead)
def update_habit(
    habit_id: int,
    data: HabitUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return habit_read(_service(db).update(habit_id, user.id, data), today)


@router.put("/{habit_id}/schedule", response_model=HabitRead)
def set_schedule(
    habit_id: int,
    data: ScheduleUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return habit_read(_service(db).set_schedule(habit_id, user.id, data, today), today)


@router.post("/{habit_id}/archive", response_model=HabitRead)
def archive_habit(
    habit_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return habit_read(_service(db).archive(habit_id, user.id, today), today)


@router.post("/{habit_id}/unarchive", response_model=HabitRead)
def unarchive_habit(
    habit_id: int,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return habit_read(_service(db).unarchive(habit_id, user.id, today), today)
