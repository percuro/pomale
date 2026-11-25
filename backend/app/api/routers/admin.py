from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_admin
from app.db.database import get_db
from app.models.user import User
from app.schemas.admin import AdminUserRead, AdminUserUpdate
from app.schemas.invitation import InvitationCreate, InvitationCreated, InvitationRead
from app.services.admin_service import AdminService
from app.services.invitation_service import InvitationService

router = APIRouter()


@router.get("/users", response_model=list[AdminUserRead])
def list_users(db: Session = Depends(get_db)):
    return AdminService(db).list_users()


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int, data: AdminUserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return AdminService(db).update_user(admin, user_id, data)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    AdminService(db).delete_user(admin, user_id)


@router.post("/users/{user_id}/password-reset", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
def create_password_reset(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """A one-time link with which the person sets a new password. Admins never see or set passwords."""
    target = AdminService(db).get_user(user_id)
    return InvitationService(db).create_password_reset(admin, target)


@router.post("/invitations", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
def create_invitation(data: InvitationCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return InvitationService(db).create_signup(admin, data.role, data.note)


@router.get("/invitations", response_model=list[InvitationRead])
def list_invitations(db: Session = Depends(get_db)):
    return InvitationService(db).list_open()


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: int, db: Session = Depends(get_db)):
    InvitationService(db).revoke(invitation_id)
