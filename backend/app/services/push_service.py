"""Devices that receive reminders: subscribe, list, remove, send a test."""

import json
from datetime import datetime

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import APP_NAME, get_push_contact, push_enabled
from app.errors import AppError
from app.models.push import SUBSCRIPTIONS_MAX, PushSubscription
from app.models.user import User
from app.repositories.push_repository import PushRepository
from app.schemas.push import PushConfigRead, PushDeviceRead, PushSubscriptionCreate
from app.services import audit_service
from app.services.devices import describe_user_agent
from app.services.i18n import resolve_locale, text
from app.services.login_rate_limiter import LoginRateLimiter
from app.services.webpush.endpoints import decode_keys, endpoint_allowed
from app.services.webpush.keys import ensure_vapid_keys
from app.services.webpush.sender import PushSender, SendResult
from app.services.webpush.vapid import Vapid

# Test notifications: 5 per account in 10 minutes
test_rate_limiter = LoginRateLimiter(window_seconds=10 * 60, name="push_test")


def require_push_enabled() -> None:
    if not push_enabled():
        raise AppError(404, "push.disabled", "Reminders are turned off on this server")


def make_sender(db: Session) -> PushSender:
    return PushSender(Vapid(ensure_vapid_keys(db), get_push_contact()))


def record_result(subscription: PushSubscription, result: SendResult, now: datetime) -> None:
    """Remember how the last push went; the caller deletes the subscription if it is gone."""
    if result.outcome == "ok":
        subscription.last_success_at = now
        subscription.last_error = None
    elif result.outcome == "failed":
        subscription.last_error = (result.reason or "failed")[:200]


def device_read(subscription: PushSubscription, current_session_id: int | None) -> PushDeviceRead:
    return PushDeviceRead(
        id=subscription.id,
        device=describe_user_agent(subscription.user_agent),
        created_at=subscription.created_at,
        last_success_at=subscription.last_success_at,
        last_error=subscription.last_error,
        current=current_session_id is not None and subscription.session_id == current_session_id,
    )


class PushService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = PushRepository(db)

    def config(self) -> PushConfigRead:
        if not push_enabled():
            return PushConfigRead(enabled=False, public_key=None)
        return PushConfigRead(enabled=True, public_key=ensure_vapid_keys(self.db).public_key)

    def devices(self, user: User, current_session_id: int | None) -> list[PushDeviceRead]:
        return [device_read(s, current_session_id) for s in self.repository.list_for_user(user.id)]

    def subscribe(
        self, user: User, data: PushSubscriptionCreate, session_id: int | None, user_agent: str | None
    ) -> tuple[PushDeviceRead, bool]:
        """Create or refresh the subscription for this endpoint. Returns (device, created)."""
        if not endpoint_allowed(data.endpoint):
            raise AppError(422, "push.endpoint_not_allowed", "This push service is not allowed on this server")
        try:
            decode_keys(data.keys.p256dh, data.keys.auth)
        except ValueError as error:
            raise AppError(422, "push.invalid_keys", "The subscription keys are invalid") from error
        if data.old_endpoint and data.old_endpoint != data.endpoint:
            self.repository.delete_endpoint_for_user(data.old_endpoint, user.id)
        subscription = self.repository.get_by_endpoint(data.endpoint)
        created = subscription is None or subscription.user_id != user.id
        if created and self.repository.count_for_user(user.id) >= SUBSCRIPTIONS_MAX:
            raise AppError(422, "push.too_many_devices", f"At most {SUBSCRIPTIONS_MAX} devices can receive reminders")
        if subscription is None:
            subscription = PushSubscription(endpoint=data.endpoint, user_id=user.id)
            self.db.add(subscription)
        # Same browser, other account (someone logged in as another person): it moves over
        subscription.user_id = user.id
        subscription.session_id = session_id
        subscription.p256dh = data.keys.p256dh
        subscription.auth = data.keys.auth
        subscription.user_agent = (user_agent or "")[:200] or None
        subscription.last_error = None
        if created:
            audit_service.record(self.db, "push.device_added", actor=user, target=user, commit=False)
        self.db.commit()
        self.db.refresh(subscription)
        return device_read(subscription, session_id), created

    def remove(self, user: User, subscription_id: int) -> None:
        subscription = self._get(user, subscription_id)
        audit_service.record(self.db, "push.device_removed", actor=user, target=user, commit=False)
        self.db.delete(subscription)
        self.db.commit()

    def send_test(self, user: User, subscription_id: int, request: Request, sender: PushSender, now: datetime):
        subscription = self._get(user, subscription_id)
        ip_address = audit_service.client_ip(request) or "unknown"
        test_rate_limiter.check(str(user.id), ip_address)
        test_rate_limiter.record_failure(str(user.id), ip_address)
        locale = resolve_locale(user, request)
        payload = {
            "title": text(locale, "push.test_title"),
            "body": text(locale, "push.test_body").format(app=APP_NAME),
            "tag": "test",
            "url": "/account",
            "habit": None,
        }
        result = sender.send(
            subscription.endpoint,
            subscription.p256dh,
            subscription.auth,
            json.dumps(payload, ensure_ascii=False).encode(),
            ttl=600,
        )
        if result.outcome == "gone":
            self.db.delete(subscription)
            self.db.commit()
            raise AppError(410, "push.gone", "This device no longer accepts notifications; it was removed")
        record_result(subscription, result, now.replace(tzinfo=None))
        self.db.commit()
        if result.outcome == "failed":
            raise AppError(
                502, "push.send_failed", "The push service did not accept the notification", reason=result.reason
            )

    def _get(self, user: User, subscription_id: int) -> PushSubscription:
        subscription = self.repository.get_for_user(subscription_id, user.id)
        if subscription is None:
            raise AppError(404, "push.not_found", "Device not found")
        return subscription
