"""One-time links: invitations to create an account and password-reset links.

The link is PUBLIC_URL/invite#<token>. The token sits in the URL fragment, so it never
reaches server logs or Referer headers; the web app reads it and sends it in the body.
Only its SHA-256 hash is stored. Using a link is atomic: the first request that marks it
as used wins, a second one finds it invalid.
"""

import secrets
from datetime import datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_invite_expiry_days, get_public_url
from app.errors import AppError
from app.models.invitation import PURPOSE_PASSWORD_RESET, PURPOSE_SIGNUP, Invitation
from app.models.user import User, UserSession
from app.repositories.auth_repository import AuthRepository
from app.schemas.invitation import InvitationAccept, InvitationCreated, InvitationInfo, InvitationRead
from app.services import audit_service
from app.services.account_settings import apply_settings
from app.services.auth_service import AuthService, normalize_username, utcnow
from app.services.login_rate_limiter import LoginRateLimiter

RESET_EXPIRY = timedelta(hours=24)
# Used and expired links are kept a while for reference, then removed
KEEP_FINISHED = timedelta(days=30)
# Wrong tokens per IP address, like the login limit
invitation_rate_limiter = LoginRateLimiter(name="invitation")


def invalid() -> AppError:
    return AppError(404, "invite.invalid", "This link is invalid, expired or already used")


class InvitationService:
    def __init__(self, db: Session):
        self.db = db
        self.auth = AuthService(AuthRepository(db))

    # --- Admin --------------------------------------------------------------

    def create_signup(self, admin: User, role: str, note: str | None) -> InvitationCreated:
        now = utcnow()
        audit_service.record(self.db, "invite.created", actor=admin, commit=False, purpose=PURPOSE_SIGNUP, role=role)
        return self._create(
            Invitation(
                purpose=PURPOSE_SIGNUP,
                role=role,
                note=note,
                created_by_user_id=admin.id,
                expires_at=now + timedelta(days=get_invite_expiry_days()),
            ),
            now,
        )

    def create_password_reset(self, admin: User, target: User) -> InvitationCreated:
        if not target.is_active:
            raise AppError(409, "admin.user_inactive", "Reactivate the account first")
        now = utcnow()
        # Only the newest reset link for an account works
        self.db.execute(
            delete(Invitation).where(
                Invitation.purpose == PURPOSE_PASSWORD_RESET,
                Invitation.target_user_id == target.id,
                Invitation.used_at.is_(None),
            )
        )
        audit_service.record(
            self.db, "invite.created", actor=admin, target=target, commit=False, purpose=PURPOSE_PASSWORD_RESET
        )
        return self._create(
            Invitation(
                purpose=PURPOSE_PASSWORD_RESET,
                target_user_id=target.id,
                created_by_user_id=admin.id,
                expires_at=now + RESET_EXPIRY,
            ),
            now,
        )

    def _create(self, invitation: Invitation, now: datetime) -> InvitationCreated:
        self.db.execute(
            delete(Invitation).where(
                or_(Invitation.used_at.is_not(None), Invitation.expires_at <= now),
                Invitation.expires_at <= now - KEEP_FINISHED,
            )
        )
        token = secrets.token_urlsafe(32)
        invitation.token_hash = AuthService.hash_token(token)
        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return InvitationCreated(
            id=invitation.id,
            purpose=invitation.purpose,
            url=f"{get_public_url()}/invite#{token}",
            expires_at=invitation.expires_at,
        )

    def list_open(self) -> list[InvitationRead]:
        now = utcnow()
        invitations = self.db.scalars(
            select(Invitation)
            .where(Invitation.used_at.is_(None), Invitation.expires_at > now)
            .order_by(Invitation.created_at.desc(), Invitation.id.desc())
        )
        names = dict(self.db.execute(select(User.id, User.username)).all())
        return [
            InvitationRead(
                id=invitation.id,
                purpose=invitation.purpose,
                role=invitation.role,
                note=invitation.note,
                target_username=names.get(invitation.target_user_id),
                created_by_username=names.get(invitation.created_by_user_id),
                created_at=invitation.created_at,
                expires_at=invitation.expires_at,
            )
            for invitation in invitations
        ]

    def revoke(self, admin: User, invitation_id: int) -> None:
        invitation = self.db.scalars(
            select(Invitation).where(Invitation.id == invitation_id, Invitation.used_at.is_(None))
        ).first()
        if invitation is None:
            raise AppError(404, "invite.not_found", "Invitation not found")
        target = self.db.get(User, invitation.target_user_id) if invitation.target_user_id else None
        audit_service.record(
            self.db, "invite.revoked", actor=admin, target=target, commit=False, purpose=invitation.purpose
        )
        self.db.delete(invitation)
        self.db.commit()

    # --- Public -------------------------------------------------------------

    def inspect(self, token: str, request: Request) -> InvitationInfo:
        invitation = self._find_valid(token, request)
        target = self.db.get(User, invitation.target_user_id) if invitation.target_user_id else None
        return InvitationInfo(
            purpose=invitation.purpose,
            username=target.username if target else None,
            expires_at=invitation.expires_at,
        )

    def accept(self, data: InvitationAccept, request: Request, response: Response) -> User:
        invitation = self._find_valid(data.token, request)
        if invitation.purpose == PURPOSE_SIGNUP:
            username = normalize_username(data.username or "")
        AuthService.check_password(data.password)
        self.claim(invitation)
        if invitation.purpose == PURPOSE_SIGNUP:
            user = self._signup(invitation, username, data)
            audit_service.record(self.db, "account.created", actor=user, target=user, via="invite", role=user.role)
        else:
            user = self._reset(invitation, data.password)
        audit_service.record(self.db, "invite.used", actor=user, target=user, purpose=invitation.purpose)
        self.auth.start_session(user, request, response)
        return user

    def claim(self, invitation: Invitation) -> None:
        """Mark the link as used (not yet committed); of two simultaneous requests only one succeeds."""
        now = utcnow()
        claimed = self.db.execute(
            update(Invitation)
            .where(Invitation.id == invitation.id, Invitation.used_at.is_(None), Invitation.expires_at > now)
            .values(used_at=now)
        ).rowcount
        if claimed != 1:
            self.db.rollback()
            raise invalid()

    def find_valid(self, token: str, request: Request) -> Invitation:
        return self._find_valid(token, request)

    def _signup(self, invitation: Invitation, username: str, data: InvitationAccept) -> User:
        if self.auth.repository.get_user_by_username(username) is not None:
            self.db.rollback()
            raise AppError(409, "account.username_taken", "This username is already taken")
        user = User(username=username, password_hash=AuthService.hash_password(data.password), role=invitation.role)
        apply_settings(user, data)
        self.db.add(user)
        try:
            self.db.flush()
            invitation.used_by_user_id = user.id
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "account.username_taken", "This username is already taken") from exc
        self.db.refresh(user)
        return user

    def _reset(self, invitation: Invitation, password: str) -> User:
        user = self.db.get(User, invitation.target_user_id)
        if user is None or not user.is_active:
            self.db.rollback()
            raise invalid()
        user.password_hash = AuthService.hash_password(password)
        invitation.used_by_user_id = user.id
        # Every device has to log in again; this browser gets a fresh session below
        self.db.execute(delete(UserSession).where(UserSession.user_id == user.id))
        self.db.commit()
        self.db.refresh(user)
        return user

    def _find_valid(self, token: str, request: Request) -> Invitation:
        ip_address = request.client.host if request.client else "unknown"
        invitation_rate_limiter.check(ip_address, ip_address)
        invitation = self.db.scalars(
            select(Invitation).where(Invitation.token_hash == AuthService.hash_token(token.strip()))
        ).first()
        if invitation is None or invitation.used_at is not None or invitation.expires_at <= utcnow():
            audit_service.record_failure(self.db, invitation_rate_limiter, ip_address, request)
            raise invalid()
        return invitation
