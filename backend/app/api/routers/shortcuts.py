from datetime import date

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_today
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.repositories.shortcut_repository import ShortcutRepository
from app.schemas.shortcut import (
    ShortcutCheckinRead,
    ShortcutCheckinRequest,
    ShortcutTokenCreate,
    ShortcutTokenCreated,
    ShortcutTokenRead,
)
from app.services.habit_service import HabitService
from app.services.shortcut_service import ShortcutService

# Bearer key only, no session: the iOS shortcut has no cookie
public_router = APIRouter()
# Key management in the logged-in web app
router = APIRouter()


def _service(db: Session) -> ShortcutService:
    return ShortcutService(ShortcutRepository(db), HabitRepository(db))


@public_router.put("/habits/{habit_id}/days/today", response_model=ShortcutCheckinRead)
def shortcut_check_in(
    habit_id: int,
    request: Request,
    data: ShortcutCheckinRequest | None = None,
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    done = data.done if data is not None else True
    return _service(db).check_in_today(request, habit_id, done, today)


@router.get("/habits/{habit_id}/shortcut-tokens", response_model=list[ShortcutTokenRead])
def list_tokens(habit_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    return ShortcutRepository(db).list_for_habit(habit_id)


@router.post(
    "/habits/{habit_id}/shortcut-tokens",
    response_model=ShortcutTokenCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_token(
    habit_id: int,
    data: ShortcutTokenCreate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    token, raw = _service(db).create(habit_id, data.label)
    return ShortcutTokenCreated(**ShortcutTokenRead.model_validate(token).model_dump(), token=raw)


@router.delete("/habits/{habit_id}/shortcut-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(habit_id: int, token_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    _service(db).revoke(habit_id, token_id)
