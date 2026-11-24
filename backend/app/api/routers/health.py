from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.database import get_db
from app.errors import AppError

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as exc:  # noqa: BLE001 - the health check reports any database error
        raise AppError(503, "health.database_unavailable", "Database not reachable") from exc
    return {"status": "ok", "version": __version__}
