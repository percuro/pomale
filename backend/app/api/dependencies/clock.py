from datetime import date

from app.config import get_default_timezone
from app.services.day_service import today_in


def get_today() -> date:
    """Today in the configured time zone. Tests replace it via dependency_overrides."""
    return today_in(get_default_timezone())
