from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.errors import AppError
from app.models.user import ROLE_ADMIN
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import AccountSettings, MeRead
from app.services import audit_service, setup_service
from app.services.account_service import me_read
from app.services.auth_service import AuthService
from app.services.login_rate_limiter import LoginRateLimiter

router = APIRouter()
setup_rate_limiter = LoginRateLimiter(name="setup")


class SetupStatus(BaseModel):
    needed: bool


class SetupRequest(AccountSettings):
    token: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


@router.get("", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db)):
    return SetupStatus(needed=setup_service.needs_setup(db))


@router.post("", response_model=MeRead)
def run_setup(
    data: SetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    ip_address = request.client.host if request.client else "unknown"
    setup_rate_limiter.check("setup", ip_address)
    if not setup_service.needs_setup(db):
        raise AppError(409, "setup.done", "Setup is already complete")
    if not setup_service.token_matches(data.token.strip()):
        audit_service.record_failure(db, setup_rate_limiter, "setup", request)
        raise AppError(403, "setup.invalid_token", "Wrong setup token")
    service = AuthService(AuthRepository(db))
    with setup_service.setup_lock():
        if not setup_service.needs_setup(db):
            raise AppError(409, "setup.done", "Setup is already complete")
        user = service.create_user(data.username, data.password, role=ROLE_ADMIN, settings=data)
    setup_service.clear_token()
    audit_service.record(db, "account.created", actor=user, target=user, via="setup", role=user.role)
    service.start_session(user, request, response)
    return me_read(user, now)
