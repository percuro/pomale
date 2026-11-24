from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = AuthService(AuthRepository(db)).current_session(request)
    # Lets the session list mark "this device"
    request.state.session_id = session.id
    return session.user
