from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.api.dependencies.demo import NOT_IN_DEMO
from app.config import password_login_enabled
from app.db.database import get_db
from app.errors import AppError
from app.models.user import User
from app.schemas.auth import AccountUpdate, MeRead, PasswordChange, PasswordConfirmation, SessionRead
from app.schemas.oidc import OidcUnlink
from app.schemas.token import TokenCreate, TokenCreated, TokenRead
from app.services.account_service import AccountService, me_read
from app.services.auth_service import clear_session_cookie, require_password_login, utcnow
from app.services.oidc_service import OidcService
from app.services.token_service import TokenService, token_read

router = APIRouter()


@router.patch("", response_model=MeRead)
def update_account(
    data: AccountUpdate,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    return me_read(AccountService(db).update(user, data), now)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, dependencies=NOT_IN_DEMO)
def delete_account(
    data: PasswordConfirmation,
    request: Request,
    response: Response,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    AccountService(db).delete(user, data.password, request, response, request.state.session_id)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, dependencies=NOT_IN_DEMO)
def change_password(
    data: PasswordChange,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    require_password_login()
    AccountService(db).change_password(
        user, data.current_password, data.new_password, request, request.state.session_id
    )


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return AccountService(db).sessions(user, utcnow(), request.state.session_id)


@router.post("/sessions/revoke-others", status_code=status.HTTP_204_NO_CONTENT, dependencies=NOT_IN_DEMO)
def revoke_other_sessions(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    AccountService(db).revoke_other_sessions(user, request.state.session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=NOT_IN_DEMO)
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


@router.delete("/oidc", status_code=status.HTTP_204_NO_CONTENT, dependencies=NOT_IN_DEMO)
def unlink_oidc(
    data: OidcUnlink,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Only while another way to sign in remains: a password, with password login turned on."""
    if not user.has_password or not password_login_enabled():
        raise AppError(409, "account.last_login_method", "This is the only way to sign in to this account")
    AccountService(db).confirm(user, data.password, request, request.state.session_id)
    OidcService(db).unlink(user, actor=user, by="self")


@router.get("/tokens", response_model=list[TokenRead])
def list_tokens(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """API keys of this account, newest first, revoked ones included."""
    return [token_read(token) for token in TokenService(db).list_for(user)]


@router.post("/tokens", response_model=TokenCreated, status_code=status.HTTP_201_CREATED, dependencies=NOT_IN_DEMO)
def create_token(data: TokenCreate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    token, raw = TokenService(db).create(user, data.label, list(data.scopes), data.habit_ids, data.expires_in_days)
    return TokenCreated(**token_read(token).model_dump(), token=raw)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    TokenService(db).revoke(user, token_id)
