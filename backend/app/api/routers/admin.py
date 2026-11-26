from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app import config
from app.api.dependencies.auth import require_admin
from app.db.database import get_db
from app.errors import AppError
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.schemas.admin import (
    AdminUserRead,
    AdminUserUpdate,
    AuditEventRead,
    AuditPage,
    BackupFileRead,
    BackupStatusRead,
)
from app.schemas.invitation import InvitationCreate, InvitationCreated, InvitationRead
from app.services import audit_service, backup_service
from app.services.admin_service import AdminService
from app.services.invitation_service import InvitationService
from app.services.oidc_service import OidcService

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


@router.delete("/users/{user_id}/oidc", status_code=status.HTTP_204_NO_CONTENT)
def unlink_oidc(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Remove the account's provider link and sign it out everywhere, e.g. when the provider account
    changed hands. Then give the person a reset link to set a password or link anew."""
    target = AdminService(db).get_user(user_id)
    OidcService(db).unlink(target, actor=admin, by="admin")
    AuthRepository(db).delete_sessions(target.id)


@router.post("/invitations", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
def create_invitation(data: InvitationCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return InvitationService(db).create_signup(admin, data.role, data.note)


@router.get("/invitations", response_model=list[InvitationRead])
def list_invitations(db: Session = Depends(get_db)):
    return InvitationService(db).list_open()


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(invitation_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    InvitationService(db).revoke(admin, invitation_id)


@router.get("/audit", response_model=AuditPage)
def list_audit_events(
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    user_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    """Newest first. user_id: only entries where the account acted or was acted on."""
    events = audit_service.list_events(db, before_id, limit + 1, user_id)
    more = len(events) > limit
    events = events[:limit]
    return AuditPage(
        events=[
            AuditEventRead(
                id=event.id,
                created_at=event.created_at,
                event=event.event,
                actor_user_id=event.actor_user_id,
                actor_username=event.actor_username,
                target_user_id=event.target_user_id,
                target_username=event.target_username,
                ip_prefix=event.ip_prefix,
                details=audit_service.details_of(event),
            )
            for event in events
        ],
        next_before_id=events[-1].id if more else None,
    )


def _backup_read(backup: backup_service.BackupFile) -> BackupFileRead:
    return BackupFileRead(name=backup.name, size=backup.size, created_at=backup.created_at)


@router.get("/backups", response_model=BackupStatusRead)
def backup_status():
    """The built-in backups. They cannot be downloaded here: admins do not see other accounts' data."""
    directory = config.get_backup_dir()
    backups = backup_service.list_backups(directory)
    return BackupStatusRead(
        enabled=config.backup_enabled(),
        time=config.get_backup_time().strftime("%H:%M"),
        timezone=config.get_default_timezone_name(),
        keep_days=config.get_backup_keep_days(),
        directory=str(directory),
        count=len(backups),
        total_size=sum(b.size for b in backups),
        latest=_backup_read(backups[0]) if backups else None,
        last_error=backup_service.state.last_error,
        last_error_at=backup_service.state.last_error_at,
    )


@router.post("/backups", response_model=BackupFileRead, status_code=status.HTTP_201_CREATED)
def create_backup(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        backup = backup_service.create_backup(config.get_backup_dir(), datetime.now(UTC), config.get_backup_keep_days())
    except Exception as exc:
        raise AppError(500, "backup.failed", "The backup failed; see the server log") from exc
    audit_service.record(db, "backup.created", actor=admin, name=backup.name)
    return _backup_read(backup)
