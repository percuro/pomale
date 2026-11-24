from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import AccountUpdate, MeRead
from app.services.account_service import AccountService, me_read

router = APIRouter()


@router.patch("", response_model=MeRead)
def update_account(
    data: AccountUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    return me_read(AccountService(db).update(user, data), now)
