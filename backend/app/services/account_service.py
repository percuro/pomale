from datetime import datetime

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.config import get_default_timezone_name
from app.errors import AppError
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import AccountUpdate, MeRead, SessionRead
from app.services import audit_service
from app.services.account_settings import apply_settings
from app.services.auth_service import AuthService, clear_session_cookie
from app.services.devices import describe_user_agent
from app.services.login_rate_limiter import login_rate_limiter
from app.services.timezones import effective_timezone_name, user_today


def me_read(user: User, now: datetime) -> MeRead:
    return MeRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        timezone=effective_timezone_name(user),
        timezone_setting=user.timezone,
        default_timezone=get_default_timezone_name(),
        locale=user.locale,
        today=user_today(user, now),
    )


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class AccountService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuthRepository(db)

    def update(self, user: User, data: AccountUpdate) -> User:
        apply_settings(user, data)
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_password(self, user: User, password: str, request: Request) -> None:
        """Re-check the password before a sensitive change; limited like the login."""
        ip_address = client_ip(request)
        login_rate_limiter.check(user.username, ip_address)
        if not AuthService.verify_password(password, user.password_hash):
            audit_service.record_failure(self.db, login_rate_limiter, user.username, request, target=user)
            # 403, not 401: the session is fine, only the confirmation failed
            raise AppError(403, "account.wrong_password", "The password is wrong")
        login_rate_limiter.record_success(user.username)

    def change_password(self, user: User, current: str, new: str, request: Request, session_id: int) -> None:
        self.verify_password(user, current, request)
        AuthService.check_password(new)
        user.password_hash = AuthService.hash_password(new)
        audit_service.record(self.db, "account.password_changed", actor=user, target=user, commit=False)
        self.db.commit()
        # Every other device has to log in again with the new password
        self.repository.delete_sessions(user.id, keep_session_id=session_id)

    def sessions(self, user: User, now: datetime, current_session_id: int) -> list[SessionRead]:
        return [
            SessionRead(
                id=session.id,
                created_at=session.created_at,
                last_seen_at=session.last_seen_at,
                device=describe_user_agent(session.user_agent),
                current=session.id == current_session_id,
            )
            for session in self.repository.list_sessions(user.id, now)
        ]

    def revoke_session(self, user: User, session_id: int) -> None:
        session = self.repository.get_session_for_user(session_id, user.id)
        if session is None:
            raise AppError(404, "session.not_found", "Session not found")
        audit_service.record(self.db, "account.sessions_revoked", actor=user, target=user, commit=False, count=1)
        self.repository.delete_session(session)

    def revoke_other_sessions(self, user: User, current_session_id: int) -> int:
        count = self.repository.delete_sessions(user.id, keep_session_id=current_session_id)
        if count:
            audit_service.record(self.db, "account.sessions_revoked", actor=user, target=user, count=count)
        return count

    def ensure_not_last_admin(self, user: User) -> None:
        if user.is_admin and user.is_active and self.repository.count_active_admins(exclude_user_id=user.id) == 0:
            raise AppError(409, "account.last_admin", "The last active admin account cannot be removed or demoted")

    def delete(self, user: User, password: str, request: Request, response: Response) -> None:
        self.verify_password(user, password, request)
        self.ensure_not_last_admin(user)
        audit_service.record(self.db, "account.deleted", actor=user, target=user, commit=False, by="self")
        self.repository.delete_user(user)
        clear_session_cookie(response)
