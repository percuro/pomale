from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.push import PushSubscription
from app.models.user import ROLE_ADMIN, User, UserSession


def _forget_devices(db: Session, sessions) -> None:
    """Remove the push subscriptions of sessions that are logged out (not of expired ones).

    A logged-out device must stop showing habit names on its lock screen.
    """
    db.execute(delete(PushSubscription).where(PushSubscription.session_id.in_(sessions)))


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username.lower()).first()

    def add_user(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        # Changing the password logs out all devices
        _forget_devices(self.db, select(UserSession.id).where(UserSession.user_id == user.id))
        self.db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        self.db.commit()

    def create_session(
        self,
        user: User,
        token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        now: datetime,
        auth_method: str,
    ) -> UserSession:
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            last_seen_at=now,
            auth_method=auth_method,
            authenticated_at=now,
        )
        user.last_seen_at = now
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, token_hash: str) -> UserSession | None:
        return self.db.query(UserSession).filter(UserSession.token_hash == token_hash).first()

    def touch_session(self, session: UserSession, expires_at: datetime | None, seen_at: datetime | None) -> None:
        if expires_at is not None:
            session.expires_at = expires_at
        if seen_at is not None:
            session.last_seen_at = seen_at
            session.user.last_seen_at = seen_at
        self.db.commit()

    def list_sessions(self, user_id: int, now: datetime) -> list[UserSession]:
        return list(
            self.db.scalars(
                select(UserSession)
                .where(UserSession.user_id == user_id, UserSession.expires_at > now)
                .order_by(UserSession.last_seen_at.desc(), UserSession.id.desc())
            )
        )

    def get_session_for_user(self, session_id: int, user_id: int) -> UserSession | None:
        return self.db.scalars(
            select(UserSession).where(UserSession.id == session_id, UserSession.user_id == user_id)
        ).first()

    def delete_sessions(self, user_id: int, keep_session_id: int | None = None) -> int:
        query = delete(UserSession).where(UserSession.user_id == user_id)
        ids = select(UserSession.id).where(UserSession.user_id == user_id)
        if keep_session_id is not None:
            query = query.where(UserSession.id != keep_session_id)
            ids = ids.where(UserSession.id != keep_session_id)
        _forget_devices(self.db, ids)
        count = self.db.execute(query).rowcount
        self.db.commit()
        return count

    def count_active_admins(self, exclude_user_id: int | None = None) -> int:
        query = select(func.count()).select_from(User).where(User.role == ROLE_ADMIN, User.is_active.is_(True))
        if exclude_user_id is not None:
            query = query.where(User.id != exclude_user_id)
        return self.db.scalar(query) or 0

    def delete_user(self, user: User) -> None:
        """Delete the account with all its data (habits, check-ins, keys, sessions cascade in the database)."""
        self.db.execute(delete(User).where(User.id == user.id))
        self.db.commit()
        self.db.expunge_all()

    def delete_session(self, session: UserSession, *, forget_devices: bool = True) -> None:
        """forget_devices=False for an expired session: its device keeps getting reminders."""
        if forget_devices:
            _forget_devices(self.db, [session.id])
        self.db.delete(session)
        self.db.commit()

    def delete_expired_sessions(self, now: datetime) -> None:
        self.db.query(UserSession).filter(UserSession.expires_at <= now).delete()
        self.db.commit()
