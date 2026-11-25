from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.errors import AppError
from app.models.oidc_state import PURPOSE_LINK, PURPOSE_LOGIN
from app.repositories.auth_repository import AuthRepository
from app.schemas.oidc import OidcRedirect, OidcStart
from app.services.account_service import AccountService
from app.services.auth_service import AuthService
from app.services.oidc_service import OidcService

router = APIRouter()


@router.post("/start", response_model=OidcRedirect)
def start(data: OidcStart, request: Request, response: Response, db: Session = Depends(get_db)):
    """login: anyone. link (connect the signed-in account) and reauth (confirm a change): signed in."""
    service = OidcService(db)
    if data.purpose == PURPOSE_LOGIN:
        return OidcRedirect(authorize_url=service.start(PURPOSE_LOGIN, request, response))
    session = AuthService(AuthRepository(db)).current_session(request)
    user = session.user
    if data.purpose == PURPOSE_LINK:
        if user.oidc_identity is not None:
            raise AppError(409, "oidc.already_linked", "This account is already linked; unlink it first")
        # Otherwise a stolen session could add a permanent way in
        AccountService(db).confirm(user, data.password, request, session.id)
    url = service.start(data.purpose, request, response, user=user, session_id=session.id, return_to=data.return_to)
    return OidcRedirect(authorize_url=url)


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """The provider sends the browser here; always answers with a redirect into the web app."""
    return OidcService(db).callback(request, code, state, error)
