from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.errors import AppError
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import LoginRequest, MeRead
from app.services.account_service import me_read
from app.services.auth_service import AuthService
from app.services.login_rate_limiter import login_rate_limiter

router = APIRouter()


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
