from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_today
from app.config import get_default_timezone_name
from app.db.database import get_db
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import LoginRequest, MeRead
from app.services.auth_service import AuthService
from app.services.login_rate_limiter import login_rate_limiter

router = APIRouter()


def _me(user, today: date) -> MeRead:
    return MeRead(username=user.username, today=today.isoformat(), timezone=get_default_timezone_name())


@router.post("/login", response_model=MeRead)
def login(
    login_in: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    username = login_in.username.lower()
    ip_address = request.client.host if request.client else "unknown"
    login_rate_limiter.check(username, ip_address)
    try:
        user = AuthService(AuthRepository(db)).login(login_in, response)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            login_rate_limiter.record_failure(username, ip_address)
        raise
    login_rate_limiter.record_success(username)
    return _me(user, today)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    AuthService(AuthRepository(db)).logout(request, response)


@router.get("/me", response_model=MeRead)
def me(user=Depends(require_user), today: date = Depends(get_today)):
    return _me(user, today)
