from fastapi import Depends

from app.config import demo_mode
from app.errors import AppError


def forbid_in_demo() -> None:
    """Actions that would spoil the shared demo account for the next visitor, or make no sense in it."""
    if demo_mode():
        raise AppError(403, "demo.not_allowed", "Not available in the demo")


NOT_IN_DEMO = [Depends(forbid_in_demo)]
