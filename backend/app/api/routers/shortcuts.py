from datetime import datetime

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.api.dependencies.demo import NOT_IN_DEMO
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.shortcut import (
    ShortcutCheckinRead,
    ShortcutCheckinRequest,
    ShortcutTokenCreate,
    ShortcutTokenCreated,
    ShortcutTokenRead,
)
from app.services.habit_service import HabitService
from app.services.shortcut_service import ShortcutService

# Registered before the days routes: "today" must not be parsed as a date
public_router = APIRouter()
# Key management in the logged-in web app
router = APIRouter()


@public_router.put("/habits/{habit_id}/days/today", response_model=ShortcutCheckinRead)
def shortcut_check_in(
    habit_id: int,
    request: Request,
    data: ShortcutCheckinRequest | None = None,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    """Check off today (the server decides the date). Meant for an API key with scope `checkin`."""
    done = data.done if data is not None else True
    amount = data.amount if data is not None else None
    return ShortcutService(db).check_in_today(request, user, habit_id, done, now, amount=amount)


@router.get("/habits/{habit_id}/shortcut-tokens", response_model=list[ShortcutTokenRead])
def list_tokens(habit_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    return ShortcutService(db).list_for(user, habit_id)


@router.post(
    "/habits/{habit_id}/shortcut-tokens",
    response_model=ShortcutTokenCreated,
    status_code=status.HTTP_201_CREATED,
    dependencies=NOT_IN_DEMO,
)
def create_token(
    habit_id: int,
    data: ShortcutTokenCreate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    token, raw = ShortcutService(db).create(user, habit_id, data.label)
    return ShortcutTokenCreated(**ShortcutTokenRead.model_validate(token).model_dump(), token=raw)


@router.delete("/habits/{habit_id}/shortcut-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(habit_id: int, token_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    HabitService(HabitRepository(db)).get(habit_id, user.id)
    ShortcutService(db).revoke(user, habit_id, token_id)
