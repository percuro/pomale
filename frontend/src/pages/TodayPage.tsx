import { Link } from 'react-router-dom';
import { errorText } from '../lib/api';
import { addDays, longDate, weekStart } from '../lib/dates';
import { STATE_ICON, STATE_LABEL } from '../lib/states';
import type { Day, HabitDays } from '../lib/types';
import { setDay, useDays } from '../hooks/useDays';
import { useSession } from '../hooks/useSession';

export function TodayPage() {
  const { today } = useSession();
  // Load the whole week: shares the offline cache with the week view and keeps
  // working across midnight while the device is offline
  const start = weekStart(today);
  const days = useDays(start, addDays(start, 6));

  if (days.isPending) return <p>Lädt …</p>;
  if (!days.data) {
    return (
      <p role="alert" className="error">
        {days.error instanceof TypeError
          ? 'Offline und für diesen Tag ist noch nichts auf dem Gerät gespeichert.'
          : errorText(days.error)}
      </p>
    );
  }

  const rows = days.data.habits
    .filter((habit) => !habit.archived)
    .map((habit) => ({ habit, day: habit.days.find((d) => d.date === today) }))
    .filter((row): row is { habit: HabitDays; day: Day } => Boolean(row.day));
  const planned = rows.filter((row) => row.day.planned);
  const unplanned = rows.filter((row) => !row.day.planned);
  const doneCount = planned.filter((row) => row.day.done).length;

  const set = (habitId: number, done: boolean, version: number) => setDay(habitId, today, done, version);

  return (
    <>
      <div className="page-head">
        <h1>Heute</h1>
        <p className="subtle">
          {longDate(today)}
          {planned.length > 0 && <> · {doneCount} von {planned.length} erledigt</>}
        </p>
      </div>

      {rows.length === 0 && (
        <p className="empty">
          Noch keine Gewohnheiten. <Link to="/gewohnheiten">Gewohnheit anlegen</Link>
        </p>
      )}

      {planned.length > 0 && (
        <ul className="today-list">
          {planned.map(({ habit, day }) => (
            <TodayRow key={habit.id} habit={habit} day={day} onSet={set} />
          ))}
        </ul>
      )}

      {unplanned.length > 0 && (
        <details className="unplanned">
          <summary>Heute nicht geplant ({unplanned.length})</summary>
          <ul className="today-list">
            {unplanned.map(({ habit, day }) => (
              <TodayRow key={habit.id} habit={habit} day={day} onSet={set} />
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

function TodayRow({
  habit,
  day,
  onSet,
}: {
  habit: HabitDays;
  day: Day;
  onSet: (habitId: number, done: boolean, version: number) => void;
}) {
  return (
    <li className={`today-row state-${day.state}`}>
      <button
        type="button"
        className="today-main"
        aria-pressed={day.done}
        onClick={() => {
          if (!day.done) onSet(habit.id, true, day.version);
        }}
      >
        <span className="state-icon" aria-hidden="true">{STATE_ICON[day.state]}</span>
        <span className="today-text">
          <span className="today-name">{habit.name}</span>
          {habit.cue && <span className="today-cue">{habit.cue}</span>}
        </span>
        <span className="state-label">
          {STATE_LABEL[day.state]}
          {day.conflict ? (
            <span className="pending"> · Konflikt</span>
          ) : (
            day.pending && <span className="pending"> · wartet auf Übertragung</span>
          )}
        </span>
      </button>
      {/* Space stays reserved so the row does not jump when checking off */}
      <button
        type="button"
        className="button undo"
        hidden={!day.done}
        aria-label={`${habit.name}: Rückgängig`}
        onClick={() => onSet(habit.id, false, day.version)}
      >
        Rückgängig
      </button>
    </li>
  );
}
