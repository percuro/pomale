from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_now
from app.db.database import get_db
from app.schemas.push import PushConfigRead, PushDeviceRead, PushSubscriptionCreate
from app.services.push_service import PushService, make_sender, require_push_enabled
from app.services.webpush.sender import PushSender

router = APIRouter()
enabled = [Depends(require_push_enabled)]


def get_push_sender(db: Session = Depends(get_db)) -> Iterator[PushSender]:
    """Overridden in tests with a sender on a mocked push service."""
    sender = make_sender(db)
    try:
        yield sender
    finally:
        sender.close()


def _session_id(request: Request) -> int | None:
    return getattr(request.state, "session_id", None)


@router.get("/config", response_model=PushConfigRead)
def push_config(db: Session = Depends(get_db)):
    return PushService(db).config()


@router.get("/subscriptions", response_model=list[PushDeviceRead], dependencies=enabled)
def list_devices(request: Request, user=Depends(require_user), db: Session = Depends(get_db)):
    return PushService(db).devices(user, _session_id(request))


@router.post("/subscriptions", response_model=PushDeviceRead, status_code=status.HTTP_201_CREATED, dependencies=enabled)
def subscribe(
    data: PushSubscriptionCreate,
    request: Request,
    response: Response,
    user=Depends(require_user),
    db: Session = Depends(get_db),
):
    device, created = PushService(db).subscribe(user, data, _session_id(request), request.headers.get("User-Agent"))
    if not created:
        response.status_code = status.HTTP_200_OK
    return device


@router.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=enabled)
def remove_device(subscription_id: int, user=Depends(require_user), db: Session = Depends(get_db)):
    PushService(db).remove(user, subscription_id)


@router.post("/subscriptions/{subscription_id}/test", status_code=status.HTTP_204_NO_CONTENT, dependencies=enabled)
def send_test(
    subscription_id: int,
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    sender: PushSender = Depends(get_push_sender),
    now: datetime = Depends(get_now),
):
    PushService(db).send_test(user, subscription_id, request, sender, now)
