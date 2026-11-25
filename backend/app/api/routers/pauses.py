from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import PauseCreate, PauseRead, PauseUpdate
from app.services.pause_service import PauseService

router = APIRouter()


def _service(db: Session) -> PauseService:
    return PauseService(HabitRepository(db))


@router.get("", response_model=list[PauseRead])
def list_pauses(user=Depends(require_user), db: Session = Depends(get_db)):
    return HabitRepository(db).list_pauses(user.id)


@router.post("", response_model=PauseRead, status_code=status.HTTP_201_CREATED)
def create_pause(data: PauseCreate, user=Depends(require_user), db: Session = Depends(get_db)):
    return _service(db).create(user.id, data)


@router.patch("/{pause_id}", response_model=PauseRead)
def update_pause(pause_id: int, data: PauseUpdate, user=Depends(require_user), db: Session = Depends(get_db)):
    return _service(db).update(pause_id, user.id, data)


@router.delete("/{pause_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pause(pause_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    _service(db).delete(pause_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
