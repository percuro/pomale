import csv
import io
from datetime import date, timedelta

from app.repositories.habit_repository import HabitRepository
from app.services.day_service import Entry, evaluate_range, week_start
from app.services.i18n import text


def _cell(value: str | None) -> str:
    """Guard against formula injection in spreadsheet programs."""
    text = value or ""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def export_csv(
    repository: HabitRepository, user_id: int, start: date | None, end: date, today: date, locale: str
) -> str:
    habits = repository.list_for_user(user_id, include_archived=True)
    starts = [s.valid_from for h in habits for s in h.schedules]
    start = start or (min(starts) if starts else today)
    end = min(end, today)
    first, last = week_start(start), week_start(end) + timedelta(days=6)
    checkins = repository.checkins_between([h.id for h in habits], first, last)
    pauses = repository.pauses_overlapping(user_id, first, last)
    entries_by_habit: dict[int, dict[date, Entry]] = {}
    for checkin in checkins:
        entries_by_habit.setdefault(checkin.habit_id, {})[checkin.local_date] = Entry(checkin.done, checkin.value)

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM: lets Excel detect UTF-8
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([text(locale, f"csv.{column}") for column in ("date", "habit", "cue", "planned", "state")])
    rows = []
    for habit in habits:
        habit_pauses = [p for p in pauses if p.habit_id is None or p.habit_id == habit.id]
        entries = entries_by_habit.get(habit.id, {})
        for info in evaluate_range(habit.schedules, entries, habit_pauses, start, end, today).days:
            if not info.planned and not info.done:
                continue
            rows.append(
                (
                    info.date.isoformat(),
                    habit.sort_order,
                    _cell(habit.name),
                    _cell(habit.cue),
                    text(locale, "csv.yes" if info.planned else "csv.no"),
                    text(locale, f"state.{info.state}"),
                )
            )
    rows.sort(key=lambda row: (row[0], row[1]))
    for row in rows:
        writer.writerow([row[0], *row[2:]])
    return buffer.getvalue()
