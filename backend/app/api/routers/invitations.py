from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.schemas.auth import MeRead
from app.schemas.invitation import InvitationAccept, InvitationInfo, InvitationToken
from app.services.account_service import me_read
from app.services.invitation_service import InvitationService

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
    return me_read(InvitationService(db).accept(data, request, response), now)
