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
    notes: dict[tuple[int, date], str] = {}
    for checkin in checkins:
        entries_by_habit.setdefault(checkin.habit_id, {})[checkin.local_date] = Entry(checkin.done, checkin.value)
        if checkin.note:
            notes[(checkin.habit_id, checkin.local_date)] = checkin.note

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM: lets Excel detect UTF-8
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    # New columns go at the end, so existing evaluations of the file keep working
    columns = ("date", "habit", "cue", "planned", "state", "value", "target", "note")
    writer.writerow([text(locale, f"csv.{column}") for column in columns])
    rows = []
    for habit in habits:
        habit_pauses = [p for p in pauses if p.habit_id is None or p.habit_id == habit.id]
        entries = entries_by_habit.get(habit.id, {})
        for info in evaluate_range(habit.schedules, entries, habit_pauses, start, end, today).days:
            note = notes.get((habit.id, info.date))
            # Leave out days without anything to say: not planned (weekly goals: not checked off)
            if info.state == "not_planned" and not note:
                continue
            rows.append(
                (
                    info.date.isoformat(),
                    habit.sort_order,
                    _cell(habit.name),
                    _cell(habit.cue),
                    text(locale, "csv.yes" if info.planned else "csv.no"),
                    text(locale, f"state.{info.state}"),
                    "" if info.value is None else str(info.value),
                    "" if info.target is None or info.goal_type == "days" else str(info.target),
                    _cell(note),
                )
            )
    rows.sort(key=lambda row: (row[0], row[1]))
    for row in rows:
        writer.writerow([row[0], *row[2:]])
    return buffer.getvalue()
