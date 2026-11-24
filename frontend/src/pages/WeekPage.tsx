import { useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { errorText } from '../lib/api';
import { WEEKDAY_LONG, WEEKDAY_SHORT, addDays, longDate, shortDate, weekStart } from '../lib/dates';
import { STATE_ICON, STATE_LABEL } from '../lib/states';
import type { Day, HabitDays } from '../lib/types';
import { setDay, useDays } from '../hooks/useDays';
import { useSession } from '../hooks/useSession';

export function WeekPage() {
  const { today } = useSession();
  const currentWeek = weekStart(today);
  const [start, setStart] = useState(currentWeek);
  const end = addDays(start, 6);
  const days = useDays(start, end);
  const [active, setActive] = useState<[number, number]>([0, 0]);
  const gridRef = useRef<HTMLDivElement>(null);

  const dates = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const habits = days.data?.habits ?? [];

  const focusCell = (row: number, col: number) => {
    const r = Math.max(0, Math.min(habits.length - 1, row));
    const c = Math.max(0, Math.min(6, col));
    setActive([r, c]);
    gridRef.current?.querySelector<HTMLButtonElement>(`[data-cell="${r}-${c}"]`)?.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const [r, c] = active;
    const moves: Record<string, [number, number]> = {
      ArrowUp: [r - 1, c],
      ArrowDown: [r + 1, c],
      ArrowLeft: [r, c - 1],
      ArrowRight: [r, c + 1],
      Home: [r, 0],
      End: [r, 6],
    };
    const target = moves[event.key];
    if (target && (event.target as HTMLElement).dataset.cell) {
      event.preventDefault();
      focusCell(...target);
    }
  };

  const toggle = (habit: HabitDays, day: Day) => {
    if (day.state === 'future') return;
    setDay(habit.id, day.date, !day.done, day.version);
  };

  return (
    <>
      <div className="page-head week-head-bar">
        <div>
          <h1>Woche</h1>
          <p className="subtle">
            {shortDate(start)} – {shortDate(end)}
            {start.slice(0, 4)}
          </p>
        </div>
        <div className="week-nav" role="group" aria-label="Woche wählen">
          <button type="button" className="button" onClick={() => setStart(addDays(start, -7))}>
            ‹ Vorwoche
          </button>
          <button
            type="button"
            className="button"
            disabled={start === currentWeek}
            onClick={() => setStart(currentWeek)}
          >
            Diese Woche
          </button>
          <button
            type="button"
            className="button"
            disabled={start >= currentWeek}
            onClick={() => setStart(addDays(start, 7))}
          >
            Nächste ›
          </button>
        </div>
      </div>

      {days.data?.offline && (
        <p className="subtle" role="status">Gespeicherter Stand – Server gerade nicht erreichbar.</p>
      )}
      {days.isPending && <p>Lädt …</p>}
      {days.isError && !days.data && <p role="alert" className="error">{errorText(days.error)}</p>}
      {days.isSuccess && habits.length === 0 && (
        <p className="empty">
          In dieser Woche gibt es keine Gewohnheiten. <Link to="/gewohnheiten">Gewohnheit anlegen</Link>
        </p>
      )}

      {habits.length > 0 && (
        <div
          className="week-grid"
          role="grid"
          aria-label={`Woche vom ${longDate(start)}`}
          aria-describedby="week-help"
          ref={gridRef}
          onKeyDown={onKeyDown}
        >
          <div role="row" className="week-row week-columns">
            <span role="columnheader" className="week-name">Gewohnheit</span>
            {dates.map((date, i) => (
              <span
                role="columnheader"
                key={date}
                className={date === today ? 'week-day is-today' : 'week-day'}
                aria-label={longDate(date)}
              >
                {WEEKDAY_SHORT[i]}
                <small>{shortDate(date)}</small>
              </span>
            ))}
          </div>
          {habits.map((habit, r) => (
            <div role="row" className="week-row" key={habit.id}>
              <span role="rowheader" className="week-name">
                <span className="week-habit">{habit.name}</span>
                <small className="quota">
                  {habit.quota.due > 0 ? `${habit.quota.done} von ${habit.quota.due}` : 'nichts fällig'}
                  {habit.archived && ' · archiviert'}
                </small>
              </span>
              {habit.days.map((day, c) => (
                <span role="gridcell" key={day.date} className={day.date === today ? 'is-today' : undefined}>
                  <button
                    type="button"
                    data-cell={`${r}-${c}`}
                    className={`cell state-${day.state}${day.pending ? ' is-pending' : ''}${day.conflict ? ' is-conflict' : ''}`}
                    tabIndex={active[0] === r && active[1] === c ? 0 : -1}
                    aria-pressed={day.state === 'future' ? undefined : day.done}
                    aria-disabled={day.state === 'future'}
                    aria-label={`${habit.name}, ${WEEKDAY_LONG[c]} ${shortDate(day.date)}: ${STATE_LABEL[day.state]}${day.conflict ? ', Konflikt' : day.pending ? ', wartet auf Übertragung' : ''}`}
                    title={`${STATE_LABEL[day.state]}${day.pending ? ' (wartet auf Übertragung)' : ''}`}
                    onFocus={() => setActive([r, c])}
                    onClick={() => toggle(habit, day)}
                  >
                    <span aria-hidden="true">{STATE_ICON[day.state]}</span>
                  </button>
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
      <p id="week-help" className="subtle help">
        Pfeiltasten wählen einen Tag, Leertaste oder Enter setzt ihn auf erledigt bzw. offen.
        Quote: erledigte von fälligen Tagen; nicht geplante und zukünftige Tage zählen nicht.
      </p>
    </>
  );
}
