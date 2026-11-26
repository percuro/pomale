from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.errors import AppError
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import SESSION_COOKIE_NAME, AuthService
from app.services.token_service import TokenService, bearer_token


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """The account behind this request: its session cookie, or else an API key (bearer).

    With a key, only the routes and habits the key allows get this far (token_service).
    A request with a cookie is always treated as a session, also if it carries a key.
    """
    raw_key = bearer_token(request) if SESSION_COOKIE_NAME not in request.cookies else None
    if raw_key is not None:
        token = TokenService(db).authenticate(request, raw_key)
        request.state.api_token = token
        request.state.session_id = None
        return token.user
    session = AuthService(AuthRepository(db)).current_session(request)
    # Lets the session list mark "this device"
    request.state.session_id = session.id
    return session.user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise AppError(403, "auth.forbidden", "Only admins may do this")
    return user
