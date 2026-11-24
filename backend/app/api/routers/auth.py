from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.config import get_registration_mode
from app.db.database import get_db
from app.errors import AppError
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import LoginRequest, MeRead
from app.schemas.invitation import RegisterRequest
from app.services import setup_service
from app.services.account_service import me_read
from app.services.auth_service import AuthService
from app.services.login_rate_limiter import LoginRateLimiter, login_rate_limiter

router = APIRouter()
# Every registration attempt counts (not only failures): at most 5 per IP address and hour
register_rate_limiter = LoginRateLimiter(window_seconds=60 * 60)


@router.post("/login", response_model=MeRead)
def login(
    login_in: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    username = login_in.username.lower()
    ip_address = request.client.host if request.client else "unknown"
    login_rate_limiter.check(username, ip_address)
    try:
        user = AuthService(AuthRepository(db)).login(login_in, request, response)
    except AppError as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            login_rate_limiter.record_failure(username, ip_address)
        raise
    login_rate_limiter.record_success(username)
    return me_read(user, now)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    AuthService(AuthRepository(db)).logout(request, response)


@router.get("/me", response_model=MeRead)
def me(user=Depends(require_user), now: datetime = Depends(get_now)):
    return me_read(user, now)


@router.post("/register", response_model=MeRead)
def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    """Only with REGISTRATION=open. New accounts get the role user."""
    if get_registration_mode() != "open":
        raise AppError(403, "registration.closed", "Registration is closed; ask an admin for an invitation")
    if setup_service.needs_setup(db):
        # Otherwise a stranger could take over a fresh instance before its operator runs the setup
        raise AppError(409, "setup.required", "The instance has not been set up yet")
    ip_address = request.client.host if request.client else "unknown"
    register_rate_limiter.check(ip_address, ip_address)
    register_rate_limiter.record_failure(ip_address, ip_address)
    service = AuthService(AuthRepository(db))
    user = service.create_user(data.username, data.password, settings=data)
    service.start_session(user, request, response)
    return me_read(user, now)
