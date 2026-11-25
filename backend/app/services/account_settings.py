from app.models.user import User
from app.schemas.auth import AccountSettings


def apply_settings(user: User, settings: AccountSettings) -> None:
    """Copy the settings that were sent (PATCH semantics: absent fields stay unchanged)."""
    for field in ("display_name", "timezone", "locale"):
        if field in settings.model_fields_set:
            setattr(user, field, getattr(settings, field))
