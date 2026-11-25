from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.errors import AppError
from app.models.invitation import PURPOSE_SIGNUP
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import AccountSettings, MeRead
from app.schemas.invitation import InvitationAccept, InvitationInfo, InvitationToken
from app.schemas.oidc import InvitationOidcStart, OidcRedirect
from app.services.account_service import me_read
from app.services.auth_service import normalize_username, require_password_login
from app.services.invitation_service import InvitationService
from app.services.oidc_service import OidcService

# Public: whoever has the link may use it once
router = APIRouter()


@router.post("/inspect", response_model=InvitationInfo)
def inspect_invitation(data: InvitationToken, request: Request, db: Session = Depends(get_db)):
    return InvitationService(db).inspect(data.token, request)


@router.post("/accept", response_model=MeRead)
def accept_invitation(
    data: InvitationAccept,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    now: datetime = Depends(get_now),
):
    require_password_login()
    return me_read(InvitationService(db).accept(data, request, response), now)


@router.post("/oidc", response_model=OidcRedirect)
def accept_invitation_with_oidc(
    data: InvitationOidcStart, request: Request, response: Response, db: Session = Depends(get_db)
):
    """Use the link with the provider instead of a password: create the account (invitation)
    or link the account anew (reset link). The link is used up only when the sign-in succeeds."""
    invitation = InvitationService(db).find_valid(data.token, request)
    if invitation.purpose == PURPOSE_SIGNUP:
        username = normalize_username(data.username or "")
        if AuthRepository(db).get_user_by_username(username) is not None:
            raise AppError(409, "account.username_taken", "This username is already taken")
        settings = AccountSettings.model_validate(data.model_dump(include={"display_name", "timezone", "locale"}))
        url = OidcService(db).start(
            "signup",
            request,
            response,
            invitation=invitation,
            payload={"username": username, "settings": settings.model_dump()},
        )
    else:
        url = OidcService(db).start("recover", request, response, invitation=invitation)
    return OidcRedirect(authorize_url=url)
