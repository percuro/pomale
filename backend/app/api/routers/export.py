from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_user_today
from app.db.database import get_db
from app.errors import AppError
from app.repositories.habit_repository import HabitRepository
from app.services.export_service import export_csv

router = APIRouter()


@router.get("/export.csv")
def export(
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    end = end or today
    if start and end < start:
        raise AppError(422, "range.end_before_start", "The end date is before the start date")
    content = export_csv(HabitRepository(db), user.id, start, end, today)
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="habits-{today.isoformat()}.csv"'},
    )
