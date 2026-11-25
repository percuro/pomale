from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import GroupCreate, GroupOrder, GroupRead, GroupUpdate
from app.services.group_service import GroupService

router = APIRouter()


def _service(db: Session) -> GroupService:
    return GroupService(HabitRepository(db))


@router.get("", response_model=list[GroupRead])
def list_groups(user=Depends(require_user), db: Session = Depends(get_db)):
    return HabitRepository(db).list_groups(user.id)


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(data: GroupCreate, user=Depends(require_user), db: Session = Depends(get_db)):
    return _service(db).create(user.id, data)


@router.put("/order", response_model=list[GroupRead])
def reorder_groups(data: GroupOrder, user=Depends(require_user), db: Session = Depends(get_db)):
    return _service(db).reorder(user.id, data)


@router.patch("/{group_id}", response_model=GroupRead)
def update_group(group_id: int, data: GroupUpdate, user=Depends(require_user), db: Session = Depends(get_db)):
    return _service(db).update(group_id, user.id, data)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    _service(db).delete(group_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
