"""JSON export and import of one account (format in schemas/export.py).

The import only goes into an account without habits, groups and pauses, and it is all or
nothing: one transaction. It is meant for moving to another instance or account, not for merging.
"""

from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.errors import AppError
from app.models.habit import Checkin, Habit, HabitGroup, HabitPause, HabitReminder, HabitSchedule
from app.models.user import User
from app.repositories.habit_repository import HabitRepository
from app.schemas.export import (
    AccountExport,
    ExportAccount,
    ExportCheckin,
    ExportGroup,
    ExportHabit,
    ExportPause,
    ExportSchedule,
    ImportResult,
)
from app.services import audit_service
from app.services.auth_service import utcnow
from app.services.timezones import is_known_timezone

# Bodies above this are refused before parsing (some years of daily data are well below 1 MB)
MAX_IMPORT_BYTES = 5 * 1024 * 1024


def export_account(db: Session, user: User, now: datetime | None = None) -> AccountExport:
    repository = HabitRepository(db)
    groups = repository.list_groups(user.id)
    group_refs = {group.id: index for index, group in enumerate(groups, start=1)}
    habits = sorted(repository.list_for_user(user.id, include_archived=True), key=lambda h: (h.sort_order, h.id))
    habit_refs = {habit.id: index for index, habit in enumerate(habits, start=1)}
    pauses = db.scalars(
        select(HabitPause).where(HabitPause.user_id == user.id).order_by(HabitPause.start_on, HabitPause.id)
    ).all()
    # One query for all check-ins instead of one per habit
    checkins: dict[int, list[Checkin]] = defaultdict(list)
    for checkin in db.scalars(
        select(Checkin).join(Habit).where(Habit.user_id == user.id).order_by(Checkin.habit_id, Checkin.local_date)
    ):
        checkins[checkin.habit_id].append(checkin)
    return AccountExport(
        app_version=__version__,
        exported_at=(now or utcnow()).replace(microsecond=0),
        account=ExportAccount(timezone=user.timezone, locale=user.locale, day_end_hour=user.day_end_hour or 0),
        groups=[ExportGroup(ref=group_refs[g.id], name=g.name, sort_order=g.sort_order) for g in groups],
        habits=[
            ExportHabit(
                ref=habit_refs[habit.id],
                name=habit.name,
                cue=habit.cue,
                sort_order=habit.sort_order,
                archived_on=habit.archived_on,
                unit=habit.unit,
                color=habit.color,
                group_ref=group_refs.get(habit.group_id) if habit.group_id is not None else None,
                created_at=habit.created_at,
                schedules=[
                    ExportSchedule(valid_from=s.valid_from, weekdays=s.weekdays, goal_type=s.goal_type, target=s.target)
                    for s in sorted(habit.schedules, key=lambda s: s.valid_from)
                ],
                reminders=[r.time for r in sorted(habit.reminders, key=lambda r: r.time)],
                checkins=[
                    ExportCheckin(date=c.local_date, done=c.done, value=c.value, note=c.note)
                    for c in checkins[habit.id]
                ],
            )
            for habit in habits
        ],
        pauses=[
            ExportPause(
                habit_ref=habit_refs.get(p.habit_id) if p.habit_id is not None else None,
                start_on=p.start_on,
                end_on=p.end_on,
                reason=p.reason,
            )
            for p in pauses
        ],
    )


def _is_empty(db: Session, user: User) -> bool:
    for model in (Habit, HabitGroup, HabitPause):
        if db.scalar(select(func.count()).select_from(model).where(model.user_id == user.id)):
            return False
    return True


def import_account(db: Session, user: User, data: AccountExport) -> ImportResult:
    if not _is_empty(db, user):
        raise AppError(409, "import.not_empty", "Import only works into an account without habits, groups and pauses")
    now = utcnow()
    try:
        groups = {}
        for item in data.groups:
            group = HabitGroup(user_id=user.id, name=item.name, sort_order=item.sort_order)
            db.add(group)
            groups[item.ref] = group
        habits = {}
        checkins = reminders = 0
        for item in data.habits:
            habit = Habit(
                user_id=user.id,
                name=item.name,
                cue=item.cue,
                sort_order=item.sort_order,
                archived_on=item.archived_on,
                unit=item.unit,
                color=item.color,
                group=groups.get(item.group_ref) if item.group_ref is not None else None,
                created_at=(item.created_at or now).replace(tzinfo=None),
            )
            habit.schedules = [
                HabitSchedule(valid_from=s.valid_from, weekdays=s.weekdays, goal_type=s.goal_type, target=s.target)
                for s in item.schedules
            ]
            habit.reminders = [HabitReminder(time=t) for t in item.reminders]
            habit.checkins = [
                Checkin(local_date=c.date, done=c.done, value=c.value, note=c.note, version=1, updated_at=now)
                for c in item.checkins
            ]
            checkins += len(item.checkins)
            reminders += len(item.reminders)
            db.add(habit)
            habits[item.ref] = habit
        # Pauses refer to habits by id
        db.flush()
        for item in data.pauses:
            db.add(
                HabitPause(
                    user_id=user.id,
                    habit_id=habits[item.habit_ref].id if item.habit_ref is not None else None,
                    start_on=item.start_on,
                    end_on=item.end_on,
                    reason=item.reason,
                )
            )
        settings = ["day_end_hour"]
        user.day_end_hour = data.account.day_end_hour
        if data.account.locale is not None:
            user.locale = data.account.locale
            settings.append("locale")
        if data.account.timezone is not None and is_known_timezone(data.account.timezone):
            user.timezone = data.account.timezone
            settings.append("timezone")
        result = ImportResult(
            groups=len(groups),
            habits=len(habits),
            checkins=checkins,
            pauses=len(data.pauses),
            reminders=reminders,
            settings=settings,
        )
        audit_service.record(
            db,
            "account.imported",
            actor=user,
            commit=False,
            habits=result.habits,
            checkins=result.checkins,
            source_version=data.app_version,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result
