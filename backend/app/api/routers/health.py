from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.database import get_db
from app.errors import AppError
from app.schemas.health import HealthRead

router = APIRouter()


@router.get("/health", response_model=HealthRead)
def health(db: Session = Depends(get_db)):
    """Liveness and database check for container health checks and monitoring; needs no login."""
    try:
        db.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as exc:  # noqa: BLE001 - the health check reports any database error
        raise AppError(503, "health.database_unavailable", "Database not reachable") from exc
    return HealthRead(status="ok", version=__version__)
