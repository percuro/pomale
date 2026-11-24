from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.repositories.auth_repository import AuthRepository
from app.services.auth_service import AuthService


def require_user(request: Request, db: Session = Depends(get_db)):
    return AuthService(AuthRepository(db)).current_user(request)
