from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies.clock import get_today
from app.config import get_default_timezone_name
from app.db.database import get_db
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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Die Einrichtung ist bereits abgeschlossen")
    if not setup_service.token_matches(data.token.strip()):
        setup_rate_limiter.record_failure("setup", ip_address)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Setup-Token ist falsch")
    service = AuthService(AuthRepository(db))
    with setup_service.setup_lock():
        if not setup_service.needs_setup(db):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Die Einrichtung ist bereits abgeschlossen"
            )
        try:
            user = service.create_user(data.username, data.password)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    setup_service.clear_token()
    service.login(LoginRequest(username=user.username, password=data.password), response)
    return MeRead(username=user.username, today=today.isoformat(), timezone=get_default_timezone_name())
