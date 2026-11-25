"""Sign-in through the OIDC provider: starting it, and finishing it in the callback.

Every start writes a short-lived OidcLoginState (what to do afterwards, PKCE verifier, nonce) and
gives the browser the raw state in a cookie. The callback only continues when the state in the URL
matches that cookie, so nobody can make a victim's browser finish a sign-in they did not start.
Accounts are matched by issuer + subject only, never by e-mail address.

The callback always answers with a redirect into the web app. Errors travel in the URL fragment
(/login#error=oidc.no_account), so they do not end up in proxy logs.
"""

import hmac
import json
import logging
import re
import secrets
from datetime import UTC, timedelta

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import OidcSettings, get_oidc_redirect_uri, get_oidc_settings, get_public_url
from app.errors import AppError
from app.models.invitation import PURPOSE_PASSWORD_RESET, PURPOSE_SIGNUP, Invitation
from app.models.oidc_state import (
    PURPOSE_LINK,
    PURPOSE_LOGIN,
    PURPOSE_REAUTH,
    PURPOSE_RECOVER,
    PURPOSE_SETUP,
    OidcLoginState,
)
from app.models.oidc_state import (
    PURPOSE_SIGNUP as STATE_SIGNUP,
)
from app.models.user import AUTH_OIDC, ROLE_ADMIN, ROLE_USER, OidcIdentity, User, UserSession
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import AccountSettings
from app.services import audit_service, setup_service
from app.services.account_settings import apply_settings
from app.services.auth_service import USERNAME_PATTERN, AuthService, cookie_settings, utcnow
from app.services.login_rate_limiter import LoginRateLimiter
from app.services.oidc_client import Identity, OidcClient, OidcError, get_client, pkce_pair

logger = logging.getLogger(__name__)

STATE_COOKIE_NAME = "pomale_oidc"
STATE_TTL = timedelta(minutes=10)
# Where the web app may be sent back to after link/reauth
RETURN_PATHS = ("/", "/account", "/admin")
# Starts and failed callbacks per IP address (each start writes a row)
oidc_rate_limiter = LoginRateLimiter(name="oidc")
oidc_rate_limiter.account_limit = oidc_rate_limiter.ip_limit = 30


def require_settings() -> OidcSettings:
    settings = get_oidc_settings()
    if settings is None:
        raise AppError(404, "oidc.disabled", "Sign-in through OIDC is not configured")
    return settings


def client_for(settings: OidcSettings) -> OidcClient:
    """Separate function so tests can plug in a fake provider."""
    return get_client(settings)


def hash_state(state: str) -> str:
    return AuthService.hash_token(state)


def _cookie_path(request: Request) -> str:
    # The API is mounted under /api; the callback lives at <root>/v1/auth/oidc/callback
    return f"{request.scope.get('root_path', '')}/v1/auth/oidc"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def suggest_username(identity: Identity) -> str:
    """A valid username from what the provider tells us (preferred_username, e-mail, else "user")."""
    candidates = [identity.preferred_username, (identity.email or "").split("@", 1)[0]]
    for candidate in candidates:
        cleaned = re.sub(r"[^a-z0-9._-]", "", (candidate or "").strip().lower())[:32]
        if USERNAME_PATTERN.match(cleaned):
            return cleaned
    return "user"


class OidcFlowError(Exception):
    """Ends a callback with a redirect to `page#error=<code>`."""

    def __init__(self, code: str, page: str = "/login"):
        super().__init__(code)
        self.code = code
        self.page = page


class OidcService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuthRepository(db)
        self.auth = AuthService(self.repository)

    # --- Start --------------------------------------------------------------

    def start(
        self,
        purpose: str,
        request: Request,
        response: Response,
        *,
        user: User | None = None,
        session_id: int | None = None,
        invitation: Invitation | None = None,
        payload: dict | None = None,
        return_to: str | None = None,
    ) -> str:
        """Remember what to do after the provider and return the URL to send the browser to."""
        settings = require_settings()
        ip_address = _client_ip(request)
        oidc_rate_limiter.check(ip_address, ip_address)
        audit_service.record_failure(self.db, oidc_rate_limiter, ip_address, request)
        client = client_for(settings)
        now = utcnow()
        self.db.execute(delete(OidcLoginState).where(OidcLoginState.expires_at <= now))
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        try:
            url = client.authorization_url(
                state=state,
                nonce=nonce,
                code_challenge=challenge,
                redirect_uri=get_oidc_redirect_uri(),
                reauth=purpose == PURPOSE_REAUTH,
            )
        except OidcError as exc:
            self.db.rollback()
            logger.warning("OIDC provider not usable: %s", exc.message)
            raise AppError(503, exc.code, "The sign-in provider cannot be reached") from exc
        self.db.add(
            OidcLoginState(
                state_hash=hash_state(state),
                purpose=purpose,
                code_verifier=verifier,
                nonce=nonce,
                user_id=user.id if user is not None else None,
                session_id=session_id,
                invitation_id=invitation.id if invitation is not None else None,
                payload=json.dumps(payload) if payload is not None else None,
                return_to=return_to if return_to in RETURN_PATHS else None,
                expires_at=now + STATE_TTL,
                created_at=now,
            )
        )
        self.db.commit()
        session_cookie = cookie_settings()
        response.set_cookie(
            STATE_COOKIE_NAME,
            state,
            max_age=int(STATE_TTL.total_seconds()),
            path=_cookie_path(request),
            secure=session_cookie["secure"],
            httponly=True,
            # Lax (never strict): the cookie must come along on the redirect back from the provider
            samesite="none" if session_cookie["samesite"] == "none" else "lax",
        )
        return url

    # --- Callback -----------------------------------------------------------

    def callback(self, request: Request, code: str | None, state: str | None, error: str | None) -> Response:
        response = RedirectResponse(get_public_url() + "/", status_code=303)
        response.delete_cookie(STATE_COOKIE_NAME, path=_cookie_path(request))
        page = "/login"
        try:
            row = self._take_state(request, state)
            page = "/account" if row.purpose in (PURPOSE_LINK, PURPOSE_REAUTH) else "/login"
            if error:
                raise OidcFlowError("oidc.denied" if error in DENIED_ERRORS else "oidc.provider_error", page)
            if not code:
                raise OidcFlowError("oidc.invalid_response", page)
            settings = require_settings()
            try:
                identity = client_for(settings).authenticate(
                    code=code,
                    code_verifier=row.code_verifier,
                    nonce=row.nonce,
                    redirect_uri=get_oidc_redirect_uri(),
                    authenticated_after=row.created_at.replace(tzinfo=UTC).timestamp()
                    if row.purpose == PURPOSE_REAUTH
                    else None,
                )
            except OidcError as exc:
                logger.warning("OIDC sign-in failed: %s", exc.message)
                raise OidcFlowError(exc.code, page) from exc
            target = self._finish(row, identity, request, response)
        except OidcFlowError as exc:
            self.db.rollback()
            if exc.code in COUNTED_ERRORS:
                audit_service.record_failure(self.db, oidc_rate_limiter, _client_ip(request), request)
            response.headers["Location"] = f"{get_public_url()}{exc.page}#error={exc.code}"
            return response
        except AppError as exc:
            self.db.rollback()
            response.headers["Location"] = f"{get_public_url()}{page}#error={exc.code}"
            return response
        response.headers["Location"] = get_public_url() + target
        return response

    def _take_state(self, request: Request, state: str | None) -> OidcLoginState:
        cookie = request.cookies.get(STATE_COOKIE_NAME)
        if not state or not cookie or not hmac.compare_digest(state.encode(), cookie.encode()):
            raise OidcFlowError("oidc.state_invalid")
        row = self.db.scalars(select(OidcLoginState).where(OidcLoginState.state_hash == hash_state(state))).first()
        if row is None:
            raise OidcFlowError("oidc.state_invalid")
        # Single use, whatever happens next
        self.db.delete(row)
        self.db.commit()
        if row.expires_at <= utcnow():
            raise OidcFlowError("oidc.state_invalid")
        return row

    def _finish(self, row: OidcLoginState, identity: Identity, request: Request, response: Response) -> str:
        handlers = {
            PURPOSE_LOGIN: self._login,
            PURPOSE_LINK: self._link,
            PURPOSE_REAUTH: self._reauth,
            STATE_SIGNUP: self._signup,
            PURPOSE_SETUP: self._setup,
            PURPOSE_RECOVER: self._recover,
        }
        return handlers[row.purpose](row, identity, request, response)

    # --- Helpers ------------------------------------------------------------

    def find_identity(self, identity: Identity) -> OidcIdentity | None:
        return self.db.scalars(
            select(OidcIdentity).where(OidcIdentity.issuer == identity.issuer, OidcIdentity.subject == identity.subject)
        ).first()

    def _refresh(self, link: OidcIdentity, identity: Identity) -> None:
        link.email = identity.email
        link.preferred_username = identity.preferred_username
        link.last_login_at = utcnow()

    def _attach(self, user: User, identity: Identity) -> OidcIdentity:
        """Link (or re-link) the account to this subject. The caller commits."""
        existing = self.find_identity(identity)
        if existing is not None and existing.user_id != user.id:
            raise OidcFlowError("oidc.already_linked", "/account")
        if existing is None:
            self.db.execute(delete(OidcIdentity).where(OidcIdentity.user_id == user.id))
            existing = OidcIdentity(user_id=user.id, issuer=identity.issuer, subject=identity.subject)
            self.db.add(existing)
        self._refresh(existing, identity)
        self.db.flush()
        return existing

    def _sign_in(self, user: User, request: Request, response: Response) -> None:
        self.auth.start_session(user, request, response, auth_method=AUTH_OIDC)

    def _new_account(self, username: str, role: str, settings: AccountSettings | None, identity: Identity) -> User:
        user = User(username=username, password_hash=None, role=role)
        if settings is not None:
            apply_settings(user, settings)
        if user.display_name is None and identity.name:
            user.display_name = identity.name
        self.db.add(user)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise OidcFlowError("account.username_taken") from exc
        return user

    @staticmethod
    def _payload(row: OidcLoginState) -> dict:
        return json.loads(row.payload) if row.payload else {}

    # --- Purposes -----------------------------------------------------------

    def _login(self, _row, identity: Identity, request: Request, response: Response) -> str:
        link = self.find_identity(identity)
        if link is not None:
            user = link.user
            if not user.is_active:
                audit_service.record(
                    self.db, "auth.login_failed", target=user, request=request, method="oidc", reason="disabled"
                )
                raise OidcFlowError("auth.account_disabled")
            self._refresh(link, identity)
            audit_service.record(self.db, "auth.login", actor=user, method="oidc")
            self._sign_in(user, request, response)
            return "/"
        settings = require_settings()
        if not settings.auto_create:
            audit_service.record(self.db, "auth.login_failed", request=request, method="oidc", reason="no_account")
            raise OidcFlowError("oidc.no_account")
        if setup_service.needs_setup(self.db):
            raise OidcFlowError("setup.required")
        user = self._new_account(self._free_username(suggest_username(identity)), ROLE_USER, None, identity)
        self._attach(user, identity)
        audit_service.record(self.db, "account.created", actor=user, target=user, commit=False, via="oidc")
        audit_service.record(self.db, "account.oidc_linked", actor=user, target=user, commit=False)
        audit_service.record(self.db, "auth.login", actor=user, method="oidc")
        self._sign_in(user, request, response)
        return "/"

    def _free_username(self, base: str) -> str:
        if self.repository.get_user_by_username(base) is None:
            return base
        for number in range(2, 1000):
            candidate = f"{base[: 32 - len(str(number)) - 1]}-{number}"
            if self.repository.get_user_by_username(candidate) is None:
                return candidate
        return f"user-{secrets.token_hex(4)}"

    def _signed_in_user(self, row: OidcLoginState) -> tuple[User, UserSession]:
        user = self.db.get(User, row.user_id) if row.user_id else None
        session = self.db.get(UserSession, row.session_id) if row.session_id else None
        if user is None or not user.is_active or session is None or session.user_id != user.id:
            raise OidcFlowError("auth.session_expired")
        return user, session

    def _link(self, row, identity: Identity, _request: Request, _response: Response) -> str:
        user, _session = self._signed_in_user(row)
        self._attach(user, identity)
        audit_service.record(self.db, "account.oidc_linked", actor=user, target=user)
        return "/account#oidc=linked"

    def _reauth(self, row, identity: Identity, _request: Request, _response: Response) -> str:
        user, session = self._signed_in_user(row)
        link = self.find_identity(identity)
        if link is None or link.user_id != user.id:
            raise OidcFlowError("oidc.wrong_account", "/account")
        self._refresh(link, identity)
        session.auth_method = AUTH_OIDC
        session.authenticated_at = utcnow()
        self.db.commit()
        return f"{row.return_to or '/account'}#reauth=ok"

    def _invitation(self, row: OidcLoginState, purpose: str) -> Invitation:
        from app.services.invitation_service import InvitationService

        invitation = self.db.get(Invitation, row.invitation_id) if row.invitation_id else None
        if invitation is None or invitation.purpose != purpose:
            raise OidcFlowError("invite.invalid")
        try:
            InvitationService(self.db).claim(invitation)
        except AppError as exc:
            raise OidcFlowError(exc.code) from exc
        return invitation

    def _signup(self, row, identity: Identity, request: Request, response: Response) -> str:
        if self.find_identity(identity) is not None:
            # Checked before the link is used up, so it can be tried with another provider account
            raise OidcFlowError("oidc.already_linked")
        payload = self._payload(row)
        username = payload.get("username", "")
        if self.repository.get_user_by_username(username) is not None:
            raise OidcFlowError("account.username_taken")
        invitation = self._invitation(row, PURPOSE_SIGNUP)
        settings = AccountSettings.model_validate(payload.get("settings") or {})
        user = self._new_account(username, invitation.role or ROLE_USER, settings, identity)
        invitation.used_by_user_id = user.id
        self._attach(user, identity)
        audit_service.record(
            self.db, "account.created", actor=user, target=user, commit=False, via="invite", role=user.role
        )
        audit_service.record(self.db, "account.oidc_linked", actor=user, target=user, commit=False)
        audit_service.record(self.db, "invite.used", actor=user, target=user, purpose=PURPOSE_SIGNUP)
        self._sign_in(user, request, response)
        return "/"

    def _setup(self, row, identity: Identity, request: Request, response: Response) -> str:
        payload = self._payload(row)
        settings = AccountSettings.model_validate(payload.get("settings") or {})
        with setup_service.setup_lock():
            if not setup_service.needs_setup(self.db):
                raise OidcFlowError("setup.done")
            user = self._new_account(payload.get("username", ""), ROLE_ADMIN, settings, identity)
            self._attach(user, identity)
            audit_service.record(
                self.db, "account.created", actor=user, target=user, commit=False, via="setup", role=user.role
            )
            audit_service.record(self.db, "account.oidc_linked", actor=user, target=user)
        setup_service.clear_token()
        self._sign_in(user, request, response)
        return "/"

    def _recover(self, row, identity: Identity, request: Request, response: Response) -> str:
        existing = self.find_identity(identity)
        invitation = self.db.get(Invitation, row.invitation_id) if row.invitation_id else None
        if existing is not None and (invitation is None or existing.user_id != invitation.target_user_id):
            raise OidcFlowError("oidc.already_linked")
        invitation = self._invitation(row, PURPOSE_PASSWORD_RESET)
        user = self.db.get(User, invitation.target_user_id)
        if user is None or not user.is_active:
            raise OidcFlowError("invite.invalid")
        invitation.used_by_user_id = user.id
        self._attach(user, identity)
        # Every device has to sign in again; this browser gets a fresh session below
        self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        audit_service.record(self.db, "account.oidc_linked", actor=user, target=user, commit=False)
        audit_service.record(self.db, "invite.used", actor=user, target=user, purpose="recover")
        self._sign_in(user, request, response)
        return "/"

    # --- Unlink -------------------------------------------------------------

    def unlink(self, user: User, actor: User, by: str) -> None:
        deleted = self.db.execute(delete(OidcIdentity).where(OidcIdentity.user_id == user.id)).rowcount
        if not deleted:
            raise AppError(404, "oidc.not_linked", "This account is not linked")
        audit_service.record(self.db, "account.oidc_unlinked", actor=actor, target=user, commit=False, by=by)
        self.db.commit()


# Provider errors that mean "the person said no" or "could not sign in"
DENIED_ERRORS = {"access_denied", "login_required", "consent_required", "interaction_required"}
# Errors that count against the per-IP limit
COUNTED_ERRORS = {"oidc.state_invalid", "oidc.invalid_response", "oidc.reauth_failed"}
