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
from app.schemas.oidc import OidcRedirect, SetupOidcStart
from app.services import audit_service, setup_service
from app.services.account_service import me_read
from app.services.auth_service import AuthService, normalize_username, require_password_login
from app.services.login_rate_limiter import LoginRateLimiter
from app.services.oidc_service import OidcService

router = APIRouter()
setup_rate_limiter = LoginRateLimiter(name="setup")


class SetupStatus(BaseModel):
    needed: bool


class SetupRequest(AccountSettings):
    token: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


def check_setup_token(token: str, request: Request, db: Session) -> None:
    ip_address = request.client.host if request.client else "unknown"
    setup_rate_limiter.check("setup", ip_address)
    if not setup_service.needs_setup(db):
        raise AppError(409, "setup.done", "Setup is already complete")
    if not setup_service.token_matches(token.strip()):
        audit_service.record_failure(db, setup_rate_limiter, "setup", request)
        raise AppError(403, "setup.invalid_token", "Wrong setup token")


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
    require_password_login()
    check_setup_token(data.token, request, db)
    service = AuthService(AuthRepository(db))
    with setup_service.setup_lock():
        if not setup_service.needs_setup(db):
            raise AppError(409, "setup.done", "Setup is already complete")
        user = service.create_user(data.username, data.password, role=ROLE_ADMIN, settings=data)
    setup_service.clear_token()
    audit_service.record(db, "account.created", actor=user, target=user, via="setup", role=user.role)
    service.start_session(user, request, response)
    return me_read(user, now)


@router.post("/oidc", response_model=OidcRedirect)
def run_setup_with_oidc(data: SetupOidcStart, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create the first admin account linked to the provider (finished in the OIDC callback)."""
    check_setup_token(data.token, request, db)
    username = normalize_username(data.username)
    settings = AccountSettings.model_validate(data.model_dump(include={"display_name", "timezone", "locale"}))
    url = OidcService(db).start(
        "setup", request, response, payload={"username": username, "settings": settings.model_dump()}
    )
    return OidcRedirect(authorize_url=url)
