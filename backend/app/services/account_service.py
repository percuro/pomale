from datetime import datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import AccountSettings, AccountUpdate, MeRead
from app.services.timezones import effective_timezone_name, user_today


def me_read(user: User, now: datetime) -> MeRead:
    return MeRead(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        timezone=effective_timezone_name(user),
        timezone_setting=user.timezone,
        locale=user.locale,
        today=user_today(user, now),
    )


def apply_settings(user: User, settings: AccountSettings | AccountUpdate) -> None:
    """Copy the settings that were sent (PATCH semantics: absent fields stay unchanged)."""
    for field in ("display_name", "timezone", "locale"):
        if field in settings.model_fields_set:
            setattr(user, field, getattr(settings, field))


class AccountService:
    def __init__(self, db: Session):
        self.db = db

    def update(self, user: User, data: AccountUpdate) -> User:
        apply_settings(user, data)
        self.db.commit()
        self.db.refresh(user)
        return user
