from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_user_today
from app.db.database import get_db
from app.errors import AppError
from app.repositories.habit_repository import HabitRepository
from app.schemas.export import AccountExport, ImportResult
from app.services.data_export import export_account, import_account
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
        headers={"Content-Disposition": f'attachment; filename="pomale-{today.isoformat()}.csv"'},
    )


@router.get("/export.json", response_model=AccountExport)
def export_json(
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    """Everything of this account in one file: habits with their plans, reminders and check-ins,
    groups, pauses and settings. It can be imported into an empty account (POST /v1/import)."""
    data = export_account(db, user)
    return JSONResponse(
        content=data.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="pomale-{today.isoformat()}.json"'},
    )


# The size of the body is limited in middleware/body_limit.py (MAX_IMPORT_BYTES)
@router.post("/import", response_model=ImportResult)
def import_json(data: AccountExport, user=Depends(require_user), db: Session = Depends(get_db)):
    """Import an export file into this account. Only into an account without habits, groups and
    pauses; all or nothing."""
    return import_account(db, user, data)
