import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response, status

from app.config import cookie_secure, env_positive_int
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import LoginRequest

SESSION_COOKIE_NAME = "habit_session"
# Long sessions: the iPhone home-screen web app has its own cookie storage;
# frequent logins would defeat checking off a habit within seconds.
SESSION_IDLE_MINUTES = env_positive_int("SESSION_IDLE_MINUTES", 30 * 24 * 60)
SESSION_ABSOLUTE_HOURS = env_positive_int("SESSION_ABSOLUTE_HOURS", 90 * 24)
MIN_PASSWORD_LENGTH = 12


def utcnow() -> datetime:
    # naive UTC, matching server_default=CURRENT_TIMESTAMP in SQLite
    return datetime.now(UTC).replace(tzinfo=None)


def cookie_settings() -> dict:
    same_site = os.getenv("COOKIE_SAMESITE", "lax").lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"
    return {
        "secure": cookie_secure(),
        "httponly": True,
        "samesite": same_site,
        "path": "/",
    }


class AuthService:
    def __init__(self, repository: AuthRepository):
        self.repository = repository

    def login(self, login_in: LoginRequest, response: Response):
        user = self.repository.get_user_by_username(login_in.username)
        if user is None or not user.is_active or not self.verify_password(login_in.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Benutzername oder Passwort ist falsch",
            )
        now = utcnow()
        self.repository.delete_expired_sessions(now)
        raw_token = secrets.token_urlsafe(48)
        self.repository.create_session(
            user.id,
            self.hash_token(raw_token),
            now + timedelta(minutes=SESSION_IDLE_MINUTES),
        )
        # Persistent cookie (max_age); iOS drops session cookies when the web app is closed
        response.set_cookie(
            SESSION_COOKIE_NAME,
            raw_token,
            max_age=SESSION_ABSOLUTE_HOURS * 3600,
            **cookie_settings(),
        )
        return user

    def logout(self, request: Request, response: Response) -> None:
        raw_token = request.cookies.get(SESSION_COOKIE_NAME)
        if raw_token:
            session = self.repository.get_session(self.hash_token(raw_token))
            if session:
                self.repository.delete_session(session)
        settings = cookie_settings()
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path=settings["path"],
            secure=settings["secure"],
            httponly=settings["httponly"],
            samesite=settings["samesite"],
        )

    def current_user(self, request: Request):
        raw_token = request.cookies.get(SESSION_COOKIE_NAME)
        if not raw_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")
        session = self.repository.get_session(self.hash_token(raw_token))
        now = utcnow()
        absolute_expiry = session.created_at + timedelta(hours=SESSION_ABSOLUTE_HOURS) if session is not None else None
        if session is None or session.expires_at <= now or (absolute_expiry is not None and absolute_expiry <= now):
            if session is not None:
                self.repository.delete_session(session)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sitzung abgelaufen")
        if not session.user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Zugang deaktiviert")
        refreshed_expiry = min(now + timedelta(minutes=SESSION_IDLE_MINUTES), absolute_expiry)
        if refreshed_expiry > session.expires_at + timedelta(minutes=1):
            self.repository.update_session_expiry(session, refreshed_expiry)
        return session.user

    def create_user(self, username: str, password: str):
        username = username.strip().lower()
        if not username:
            raise ValueError("Benutzername fehlt")
        if self.repository.get_user_by_username(username) is not None:
            raise ValueError("Benutzername existiert bereits")
        self._check_password(password)
        return self.repository.create_user(username, self.hash_password(password))

    def set_password(self, username: str, password: str) -> None:
        user = self.repository.get_user_by_username(username)
        if user is None:
            raise ValueError("Benutzer nicht gefunden")
        self._check_password(password)
        self.repository.set_password(user, self.hash_password(password))

    @staticmethod
    def _check_password(password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen")

    @staticmethod
    def hash_password(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return (
            "scrypt$16384$8$1$"
            + base64.urlsafe_b64encode(salt).decode()
            + "$"
            + base64.urlsafe_b64encode(digest).decode()
        )

    @staticmethod
    def verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, n, r, p, salt_text, digest_text = encoded.split("$")
            if algorithm != "scrypt":
                return False
            salt = base64.urlsafe_b64decode(salt_text)
            expected = base64.urlsafe_b64decode(digest_text)
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(expected),
            )
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
