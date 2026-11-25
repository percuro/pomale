from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.errors import AppError
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = AuthService(AuthRepository(db)).current_session(request)
    # Lets the session list mark "this device"
    request.state.session_id = session.id
    return session.user


def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise AppError(403, "auth.forbidden", "Only admins may do this")
    return user
