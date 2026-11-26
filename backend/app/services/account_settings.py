from app.models.user import User
from app.schemas.auth import AccountSettings


def apply_settings(user: User, settings: AccountSettings) -> None:
    """Copy the settings that were sent (PATCH semantics: absent fields stay unchanged)."""
    # day_end_hour only exists on AccountUpdate; on sign-up it is never in model_fields_set
    for field in ("display_name", "timezone", "locale", "day_end_hour"):
        if field in settings.model_fields_set:
            setattr(user, field, getattr(settings, field))
