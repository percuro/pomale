from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_user
from app.api.dependencies.clock import get_user_today
from app.db.database import get_db
from app.repositories.habit_repository import HabitRepository
from app.schemas.habit import (
    CheckinRead,
    CheckinUpdate,
    DaysRead,
    HistoryRead,
    NoteRead,
    NoteUpdate,
    TodayHabitRead,
    TodayRead,
)
from app.services.checkin_service import CheckinService
from app.services.day_service import week_start
from app.services.habit_service import HabitService
from app.services.i18n import progress_text, resolve_locale, text
from app.services.timezones import effective_timezone_name
from app.services.token_service import allowed_habit_ids

router = APIRouter()


@router.get("/days", response_model=DaysRead)
def list_days(
    request: Request,
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    start = start or week_start(today)
    end = end or start + timedelta(days=6)
    result = CheckinService(HabitRepository(db)).days(user.id, start, end, today, effective_timezone_name(user))
    allowed = allowed_habit_ids(request)
    if allowed is not None:
        result.habits = [habit for habit in result.habits if habit.id in allowed]
    return result


# States that count as due today; "partial" is a quantity below its target
OPEN_STATES = ("open", "partial")
DUE_STATES = (*OPEN_STATES, "done")


@router.get("/today", response_model=TodayRead)
def today_summary(
    request: Request,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    """What is still open today. Meant for an iOS shortcut or a home automation with a `read` key:
    `message` can be spoken or shown as is."""
    days = CheckinService(HabitRepository(db)).days(user.id, today, today, today, effective_timezone_name(user))
    allowed = allowed_habit_ids(request)
    locale = resolve_locale(user, request)
    due = done = 0
    still_open: list[TodayHabitRead] = []
    for habit in days.habits:
        # Habits archived today are still in `days` (for the week view), but nothing is due for them
        if habit.archived or (allowed is not None and habit.id not in allowed):
            continue
        day = habit.days[0]
        if day.state not in DUE_STATES:
            continue
        due += 1
        if day.state not in OPEN_STATES:
            done += 1
            continue
        week = (habit.week.done, habit.week.target) if habit.week is not None else None
        progress = progress_text(locale, day.goal_type, day.value, day.target, habit.unit, week)
        still_open.append(
            TodayHabitRead(
                id=habit.id,
                name=habit.name,
                cue=habit.cue,
                goal_type=day.goal_type,
                state=day.state,
                value=day.value,
                target=day.target,
                unit=habit.unit,
                week=habit.week,
                progress=progress,
            )
        )
    if still_open:
        items = ", ".join(f"{h.name} ({h.progress})" if h.progress else h.name for h in still_open)
        message = text(locale, "today.open").format(items=items)
    else:
        message = text(locale, "today.all_done" if due else "today.nothing_due")
    return TodayRead(date=today, due=due, done=done, open=still_open, message=message)


@router.get("/history", response_model=HistoryRead)
def history(
    start: date | None = Query(default=None, alias="from"),
    end: date | None = Query(default=None, alias="to"),
    habit_id: int | None = None,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    return CheckinService(HabitRepository(db)).history(user.id, start, end, today, habit_id)


@router.put("/habits/{habit_id}/days/{day}", response_model=CheckinRead)
def set_day(
    habit_id: int,
    day: date,
    data: CheckinUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    repository = HabitRepository(db)
    habit = HabitService(repository).get(habit_id, user.id)
    return CheckinService(repository).set_state(
        habit, day, today, done=data.done, value=data.value, op_id=data.op_id, base_version=data.base_version
    )


@router.put("/habits/{habit_id}/days/{day}/note", response_model=NoteRead)
def set_note(
    habit_id: int,
    day: date,
    data: NoteUpdate,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    today: date = Depends(get_user_today),
):
    repository = HabitRepository(db)
    habit = HabitService(repository).get(habit_id, user.id)
    return CheckinService(repository).set_note(habit, day, data.note, today)
