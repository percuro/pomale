"""Personal API tokens: a bearer key that may read and/or check off for its owner, nothing else.

Deny by default: a token only reaches the routes in TOKEN_ROUTES, with the scope given there.
Account, devices, tokens and administration are never reachable with a token, and every route
added later stays closed until it is listed here (tests/test_tokens.py checks every route).

A token limited to some habits sees and changes only those: routes with a habit in the path
check it, the lists in FILTERED_ROUTES are filtered, and routes whose answers sum up all habits
(history, exports, groups, pauses) need a token for all habits.
"""

import hashlib
import secrets
from datetime import timedelta

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.routing import compile_path

from app.errors import AppError
from app.models.api_token import SCOPE_CHECKIN, SCOPE_READ, SCOPES, ApiToken
from app.models.habit import Habit
from app.models.user import User
from app.schemas.token import TokenRead
from app.services import audit_service
from app.services.auth_service import utcnow
from app.services.login_rate_limiter import LoginRateLimiter

TOKEN_PREFIX = "pm_"
# Shortcut keys of 0.3–0.9; they keep working (only the hash is compared)
LEGACY_PREFIX = "ht_"
TOKENS_PER_ACCOUNT = 50
EXPIRY_DAYS = (30, 90, 365)
# last_used_at is written at most this often, like a session's last_seen_at
LAST_USED_INTERVAL = timedelta(minutes=5)

TOKEN_ROUTES: dict[tuple[str, str], str] = {
    ("GET", "/v1/days"): SCOPE_READ,
    ("GET", "/v1/habits"): SCOPE_READ,
    ("GET", "/v1/today"): SCOPE_READ,
    ("GET", "/v1/groups"): SCOPE_READ,
    ("GET", "/v1/pauses"): SCOPE_READ,
    ("GET", "/v1/history"): SCOPE_READ,
    ("GET", "/v1/export.csv"): SCOPE_READ,
    ("GET", "/v1/export.json"): SCOPE_READ,
    ("PUT", "/v1/habits/{habit_id}/days/{day}"): SCOPE_CHECKIN,
    ("PUT", "/v1/habits/{habit_id}/days/{day}/note"): SCOPE_CHECKIN,
    ("PUT", "/v1/habits/{habit_id}/days/today"): SCOPE_CHECKIN,
}
# Lists that a token limited to some habits gets filtered
FILTERED_ROUTES = {"/v1/days", "/v1/habits", "/v1/today"}
# Matched against the request path below the /api mount: the router keeps the templates of included
# routes without their prefix, so request.scope["route"] cannot tell "/v1/habits" from "/v1/groups"
_PATTERNS = [(method, template, compile_path(template)[0]) for method, template in TOKEN_ROUTES]

# Wrong keys per IP address; a token has 256 random bits, so this only keeps the log quiet
token_rate_limiter = LoginRateLimiter(name="token", account_limit=20, ip_limit=20)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(request: Request) -> str | None:
    value = request.headers.get("Authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _invalid() -> AppError:
    return AppError(401, "token.invalid", "Key is invalid, expired or revoked", headers={"WWW-Authenticate": "Bearer"})


def token_read(token: ApiToken) -> TokenRead:
    return TokenRead(
        id=token.id,
        label=token.label,
        scopes=sorted(token.scope_set, key=SCOPES.index),
        habit_ids=token.habit_ids,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        expires_at=token.expires_at,
        revoked_at=token.revoked_at,
    )


def token_for(request: Request) -> ApiToken | None:
    """The token of this request, or None when it came with a session."""
    return getattr(request.state, "api_token", None)


def allowed_habit_ids(request: Request) -> set[int] | None:
    """The habits this request may see; None = all of the account's habits."""
    token = token_for(request)
    if token is None or not token.habits:
        return None
    return set(token.habit_ids)


class TokenService:
    def __init__(self, db: Session):
        self.db = db

    # ---- authentication -------------------------------------------------------------------

    def authenticate(self, request: Request, raw: str) -> ApiToken:
        ip_address = audit_service.client_ip(request) or "unknown"
        token_rate_limiter.check(ip_address, ip_address)
        token = self.db.scalars(select(ApiToken).where(ApiToken.token_hash == hash_token(raw))).first()
        now = utcnow()
        if (
            token is None
            or token.revoked_at is not None
            or (token.expires_at is not None and token.expires_at <= now)
            or not token.user.is_active
        ):
            audit_service.record_failure(self.db, token_rate_limiter, ip_address, request)
            raise _invalid()
        self._authorize(request, token)
        if token.last_used_at is None or now - token.last_used_at >= LAST_USED_INTERVAL:
            token.last_used_at = now
            self.db.commit()
        return token

    @staticmethod
    def _route_template(request: Request) -> str | None:
        path = request.scope["path"]
        root = request.scope.get("root_path", "")
        if root and path.startswith(root):
            path = path[len(root) :]
        for method, template, pattern in _PATTERNS:
            if method == request.method and pattern.match(path):
                return template
        return None

    @classmethod
    def _authorize(cls, request: Request, token: ApiToken) -> None:
        path = cls._route_template(request)
        scope = TOKEN_ROUTES.get((request.method, path)) if path else None
        if scope is None:
            raise AppError(403, "token.not_allowed", "API keys cannot use this endpoint")
        if scope not in token.scope_set:
            raise AppError(403, "token.missing_scope", f"This key lacks the scope '{scope}'", scope=scope)
        if not token.habits:
            return
        habit_id = request.path_params.get("habit_id")
        if habit_id is not None:
            if int(habit_id) not in token.habit_ids:
                raise AppError(403, "token.habit_not_allowed", "This key is not allowed for this habit")
        elif path not in FILTERED_ROUTES:
            raise AppError(403, "token.all_habits_needed", "Only a key for all habits can use this endpoint")

    # ---- management (session only) --------------------------------------------------------

    def list_for(self, user: User) -> list[ApiToken]:
        query = (
            select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at.desc(), ApiToken.id.desc())
        )
        return list(self.db.scalars(query))

    def get(self, user: User, token_id: int) -> ApiToken:
        token = self.db.scalars(select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user.id)).first()
        if token is None:
            raise AppError(404, "token.not_found", "Key not found")
        return token

    def create(
        self,
        user: User,
        label: str,
        scopes: list[str],
        habit_ids: list[int],
        expires_in_days: int | None = None,
    ) -> tuple[ApiToken, str]:
        scopes = sorted(set(scopes), key=SCOPES.index)
        if not scopes or any(scope not in SCOPES for scope in scopes):
            raise AppError(422, "token.invalid_scopes", "Choose at least one of: read, checkin")
        if expires_in_days is not None and expires_in_days not in EXPIRY_DAYS:
            raise AppError(422, "token.invalid_expiry", "Expiry must be 30, 90 or 365 days, or none")
        active = self.db.scalar(
            select(func.count()).select_from(ApiToken).where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
        )
        if active >= TOKENS_PER_ACCOUNT:
            raise AppError(409, "token.limit_reached", f"At most {TOKENS_PER_ACCOUNT} active keys per account")
        habits = []
        if habit_ids:
            wanted = set(habit_ids)
            habits = list(self.db.scalars(select(Habit).where(Habit.user_id == user.id, Habit.id.in_(wanted))))
            if len(habits) != len(wanted):
                raise AppError(404, "habit.not_found", "Habit not found")
        raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
        now = utcnow()
        token = ApiToken(
            user_id=user.id,
            label=label.strip() or "API",
            token_hash=hash_token(raw),
            scopes=",".join(scopes),
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days) if expires_in_days else None,
            habits=habits,
        )
        self.db.add(token)
        audit_service.record(
            self.db,
            "token.created",
            actor=user,
            commit=False,
            label=token.label,
            scopes=token.scopes,
            habits=len(habits) or "all",
        )
        self.db.commit()
        self.db.refresh(token)
        return token, raw

    def revoke(self, user: User, token_id: int) -> None:
        token = self.get(user, token_id)
        if token.revoked_at is not None:
            return
        token.revoked_at = utcnow()
        audit_service.record(self.db, "token.revoked", actor=user, commit=False, label=token.label)
        self.db.commit()
