"""Audit log: security-relevant events that admins can review.

Entries copy the usernames involved, so they stay readable after an account is deleted.
They never contain passwords or tokens. IP addresses are stored only shortened
(IPv4 /24, IPv6 /48) and only for failed logins and rate-limit blocks.
Entries older than AUDIT_RETENTION_DAYS are removed, at most once an hour, when a new one is written.
"""

import ipaddress
import json
from datetime import datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Any

from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_audit_retention_days
from app.models.audit_event import AuditEvent
from app.models.user import User
from app.services.auth_service import utcnow
from app.services.login_rate_limiter import LoginRateLimiter

PRUNE_INTERVAL_SECONDS = 60 * 60
_prune_lock = Lock()
_last_prune: float | None = None


def ip_prefix(address: str | None) -> str | None:
    """203.0.113.7 -> 203.0.113.0/24, 2001:db8:1:2::5 -> 2001:db8:1::/48; anything else -> None."""
    try:
        ip = ipaddress.ip_address(address or "")
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    prefix = 24 if ip.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def record(
    db: Session,
    event: str,
    *,
    actor: User | None = None,
    target: User | None = None,
    request: Request | None = None,
    commit: bool = True,
    **details: Any,
) -> None:
    """Add an entry. With commit=False it is written together with the caller's next commit.

    Pass `request` only for failed logins and rate-limit blocks: then the shortened IP is stored.
    """
    db.add(
        AuditEvent(
            created_at=utcnow(),
            event=event,
            actor_user_id=actor.id if actor is not None else None,
            actor_username=actor.username if actor is not None else None,
            target_user_id=target.id if target is not None else None,
            target_username=target.username if target is not None else None,
            ip_prefix=ip_prefix(client_ip(request)) if request is not None else None,
            details=json.dumps(details, ensure_ascii=False, sort_keys=True) if details else None,
        )
    )
    # The session does not autoflush: write the row now, before e.g. a bulk DELETE of the account
    db.flush()
    _maybe_prune(db)
    if commit:
        db.commit()


def record_failure(
    db: Session,
    limiter: LoginRateLimiter,
    key: str,
    request: Request,
    *,
    target: User | None = None,
) -> None:
    """Count a failed attempt; log `auth.rate_limited` once when this attempt reaches the limit."""
    ip_address = client_ip(request) or "unknown"
    if limiter.record_failure(key, ip_address):
        record(db, "auth.rate_limited", target=target, request=request, limiter=limiter.name)


def prune(db: Session, now: datetime | None = None) -> int:
    cutoff = (now or utcnow()) - timedelta(days=get_audit_retention_days())
    return db.execute(delete(AuditEvent).where(AuditEvent.created_at < cutoff)).rowcount


def _maybe_prune(db: Session) -> None:
    global _last_prune
    with _prune_lock:
        now = monotonic()
        if _last_prune is not None and now - _last_prune < PRUNE_INTERVAL_SECONDS:
            return
        _last_prune = now
    prune(db)


def list_events(db: Session, before_id: int | None, limit: int, user_id: int | None) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if before_id is not None:
        query = query.where(AuditEvent.id < before_id)
    if user_id is not None:
        query = query.where((AuditEvent.actor_user_id == user_id) | (AuditEvent.target_user_id == user_id))
    return list(db.scalars(query))


def details_of(event: AuditEvent) -> dict[str, Any]:
    return json.loads(event.details) if event.details else {}
