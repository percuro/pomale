from datetime import date

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.clock import get_today
from app.config import get_default_timezone_name
from app.db.database import get_db
from app.errors import AppError
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import LoginRequest, MeRead
from app.services import setup_service
from app.services.auth_service import AuthService
from app.services.login_rate_limiter import LoginRateLimiter

router = APIRouter()
setup_rate_limiter = LoginRateLimiter()


class SetupStatus(BaseModel):
    needed: bool


class SetupRequest(BaseModel):
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
    today: date = Depends(get_today),
):
    ip_address = request.client.host if request.client else "unknown"
    setup_rate_limiter.check("setup", ip_address)
    if not setup_service.needs_setup(db):
        raise AppError(409, "setup.done", "Setup is already complete")
    if not setup_service.token_matches(data.token.strip()):
        setup_rate_limiter.record_failure("setup", ip_address)
        raise AppError(403, "setup.invalid_token", "Wrong setup token")
    service = AuthService(AuthRepository(db))
    with setup_service.setup_lock():
        if not setup_service.needs_setup(db):
            raise AppError(409, "setup.done", "Setup is already complete")
        user = service.create_user(data.username, data.password)
    setup_service.clear_token()
    service.login(LoginRequest(username=user.username, password=data.password), response)
    return MeRead(username=user.username, today=today.isoformat(), timezone=get_default_timezone_name())
