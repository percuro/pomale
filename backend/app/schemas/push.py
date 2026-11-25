from datetime import datetime

from pydantic import BaseModel, Field


class PushConfigRead(BaseModel):
    enabled: bool
    # applicationServerKey for PushManager.subscribe (base64url); None when push is off
    public_key: str | None


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=100)
    auth: str = Field(max_length=40)


class PushSubscriptionCreate(BaseModel):
    """What PushSubscription.toJSON() returns in the browser, plus the endpoint it replaces."""

    endpoint: str = Field(max_length=1000)
    keys: PushKeys
    # Set by the service worker after "pushsubscriptionchange": the old subscription is replaced
    old_endpoint: str | None = Field(default=None, max_length=1000)


class PushDeviceRead(BaseModel):
    id: int
    device: str | None
    created_at: datetime
    last_success_at: datetime | None
    last_error: str | None
    # Registered from the session making this request
    current: bool
