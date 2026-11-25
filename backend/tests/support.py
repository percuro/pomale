"""Test environment: in-memory SQLite, fixed clock, TestClient with a logged-in user."""

import secrets
from datetime import UTC, date, datetime, time, timedelta
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.dependencies.clock import get_now
from app.db.database import Base, configure_sqlite, get_db
from app.main import app
from app.models.user import User, UserSession
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import SESSION_COOKIE_NAME, AuthService, utcnow
from app.services.login_rate_limiter import login_rate_limiter

PASSWORD = "sicheres-passwort-123"
TEST_ORIGIN = "http://localhost:5173"
# Independent of the surrounding environment (e.g. docker compose run with production
# values): CSRF on, allowed origin = the test clients' origin, default time zone.
TEST_ENV = {
    "PUBLIC_URL": TEST_ORIGIN,
    "CSRF_PROTECTION": "true",
    "COOKIE_SECURE": "false",
    "CORS_ORIGINS": "",
    "DEFAULT_TIMEZONE": "",
    "TRACKER_TZ": "",
    "OIDC_ISSUER": "",
    "OIDC_CLIENT_ID": "",
    "OIDC_CLIENT_SECRET": "",
    "OIDC_SCOPES": "",
    "OIDC_LABEL": "",
    "OIDC_AUTO_CREATE": "",
    "PASSWORD_LOGIN": "",
    "REGISTRATION": "",
    "PUSH_ENABLED": "",
    "PUSH_CONTACT": "",
    "PUSH_ALLOWED_HOSTS": "",
}


class ApiTestEnvironment:
    def __init__(self, today: date = date(2026, 11, 24)):
        # The fixed "now"; tests either set `now` directly or `today` (noon UTC of that day)
        self.now: datetime = datetime.combine(today, time(12, 0), tzinfo=UTC)
        self._env = mock.patch.dict("os.environ", TEST_ENV)
        self._env.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        configure_sqlite(self.engine)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False)
        login_rate_limiter.reset()

        def _db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_now] = lambda: self.now

    @property
    def today(self) -> date:
        return self.now.date()

    @today.setter
    def today(self, value: date) -> None:
        self.now = datetime.combine(value, time(12, 0), tzinfo=UTC)

    def create_user(self, username: str = "alex", password: str = PASSWORD, role: str = "user", **settings):
        db = self.SessionLocal()
        try:
            user = AuthService(AuthRepository(db)).create_user(username, password, role=role)
            for name, value in settings.items():
                setattr(user, name, value)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user
        finally:
            db.close()

    def client(self, username: str | None = "alex", password: str = PASSWORD) -> TestClient:
        client = TestClient(app, headers={"X-Habit-CSRF": "1", "Origin": TEST_ORIGIN})
        if username:
            response = client.post("/v1/auth/login", json={"username": username, "password": password})
            assert response.status_code == 200, response.text
        return client

    def create_passwordless_user(self, username: str, role: str = "user"):
        """An account that signs in through OIDC only."""
        user = self.create_user(username, role=role)
        db = self.SessionLocal()
        try:
            db.query(User).filter(User.id == user.id).update({"password_hash": None})
            db.commit()
        finally:
            db.close()
        return user

    def session_client(self, user, auth_method: str = "oidc", authenticated_at: datetime | None = None) -> TestClient:
        """A client with a session as if opened by the given method (e.g. an OIDC login)."""
        raw = secrets.token_urlsafe(32)
        now = utcnow()
        db = self.SessionLocal()
        try:
            db.add(
                UserSession(
                    user_id=user.id,
                    token_hash=AuthService.hash_token(raw),
                    expires_at=now + timedelta(days=1),
                    auth_method=auth_method,
                    authenticated_at=authenticated_at or now,
                )
            )
            db.commit()
        finally:
            db.close()
        client = TestClient(app, headers={"X-Habit-CSRF": "1", "Origin": TEST_ORIGIN})
        client.cookies.set(SESSION_COOKIE_NAME, raw)
        return client

    def close(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self._env.stop()
