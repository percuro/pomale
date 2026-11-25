"""Send one encrypted message to one push subscription."""

import logging
from dataclasses import dataclass
from typing import Literal

import httpx

from app.services.webpush.crypto import encrypt
from app.services.webpush.endpoints import decode_keys, endpoint_allowed
from app.services.webpush.vapid import Vapid

TIMEOUT_SECONDS = 10
# An old reminder is worthless; the push service drops it after this
DEFAULT_TTL = 2 * 3600

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendResult:
    # gone = the subscription no longer exists (404/410) and should be deleted
    outcome: Literal["ok", "gone", "failed"]
    status: int | None = None
    reason: str = ""


class PushSender:
    def __init__(self, vapid: Vapid, client: httpx.Client | None = None):
        self.vapid = vapid
        # No redirects: a push service answers directly, anything else is not followed
        self.client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)

    def close(self) -> None:
        self.client.close()

    def send(
        self,
        endpoint: str,
        p256dh: str,
        auth: str,
        payload: bytes,
        *,
        ttl: int = DEFAULT_TTL,
        topic: str | None = None,
        urgency: str = "normal",
    ) -> SendResult:
        # Checked again here: the allow-list may have changed since the device subscribed
        if not endpoint_allowed(endpoint):
            return SendResult("failed", reason="endpoint not allowed")
        try:
            ua_public, auth_secret = decode_keys(p256dh, auth)
            body = encrypt(payload, ua_public, auth_secret)
        except ValueError as exc:
            return SendResult("failed", reason=str(exc)[:200])
        headers = {
            "Authorization": self.vapid.authorization(endpoint),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(ttl),
            "Urgency": urgency,
        }
        if topic:
            headers["Topic"] = topic
        try:
            response = self.client.post(endpoint, content=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("Push to %s failed: %s", endpoint.split("/")[2], type(exc).__name__)
            return SendResult("failed", reason=type(exc).__name__)
        if response.status_code in (200, 201, 202):
            return SendResult("ok", response.status_code)
        if response.status_code in (404, 410):
            return SendResult("gone", response.status_code)
        logger.warning("Push to %s answered HTTP %s", endpoint.split("/")[2], response.status_code)
        return SendResult("failed", response.status_code, f"HTTP {response.status_code}")
