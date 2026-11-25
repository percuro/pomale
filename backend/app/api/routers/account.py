from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import AccountUpdate, MeRead, PasswordChange, PasswordConfirmation, SessionRead
from app.services.account_service import AccountService, me_read
from app.services.auth_service import clear_session_cookie, utcnow

router = APIRouter()


@router.patch("", response_model=MeRead)
def update_account(
    data: AccountUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    return me_read(AccountService(db).update(user, data), now)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    data: PasswordConfirmation,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    AccountService(db).delete(user, data.password, request, response)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: PasswordChange,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    AccountService(db).change_password(
        user, data.current_password, data.new_password, request, request.state.session_id
    )


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return AccountService(db).sessions(user, utcnow(), request.state.session_id)


@router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT)
def revoke_other_sessions(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    AccountService(db).revoke_other_sessions(user, request.state.session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: int,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    AccountService(db).revoke_session(user, session_id)
    if session_id == request.state.session_id:
        clear_session_cookie(response)
