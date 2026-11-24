from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User, UserSession


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username.lower()).first()

    def create_user(self, username: str, password_hash: str) -> User:
        user = User(username=username.lower(), password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def set_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        # Changing the password logs out all devices
        self.db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        self.db.commit()

    def create_session(self, user_id: int, token_hash: str, expires_at: datetime) -> UserSession:
        session = UserSession(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, token_hash: str) -> UserSession | None:
        return self.db.query(UserSession).filter(UserSession.token_hash == token_hash).first()

    def update_session_expiry(self, session: UserSession, expires_at: datetime) -> None:
        session.expires_at = expires_at
        self.db.commit()

    def delete_session(self, session: UserSession) -> None:
        self.db.delete(session)
        self.db.commit()

    def delete_expired_sessions(self, now: datetime) -> None:
        self.db.query(UserSession).filter(UserSession.expires_at <= now).delete()
        self.db.commit()
