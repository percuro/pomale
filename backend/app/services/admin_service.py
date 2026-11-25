from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.user import ROLE_USER, User
from app.repositories.auth_repository import AuthRepository
from app.schemas.admin import AdminUserUpdate
from app.services.account_service import AccountService


class AdminService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AuthRepository(db)
        self.accounts = AccountService(db)

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.username)))

    def get_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise AppError(404, "account.not_found", "Account not found")
        return user

    def update_user(self, admin: User, user_id: int, data: AdminUserUpdate) -> User:
        user = self.get_user(user_id)
        demote = data.role == ROLE_USER and user.is_admin
        deactivate = data.is_active is False and user.is_active
        if deactivate and user.id == admin.id:
            raise AppError(409, "admin.self_deactivate", "You cannot deactivate your own account")
        if demote or deactivate:
            self.accounts.ensure_not_last_admin(user)
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        self.db.commit()
        if deactivate:
            # Logged out everywhere at once; shortcut keys stop working while deactivated
            self.repository.delete_sessions(user.id)
        self.db.refresh(user)
        return user

    def delete_user(self, admin: User, user_id: int) -> None:
        user = self.get_user(user_id)
        if user.id == admin.id:
            # Deleting yourself needs your password: use DELETE /account
            raise AppError(409, "admin.self_delete", "Delete your own account on the account page")
        self.accounts.ensure_not_last_admin(user)
        self.repository.delete_user(user)
