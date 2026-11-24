import { APP_NAME } from '../app/brand';
import { useState, type FormEvent } from 'react';
import { errorText } from '../lib/api';
import { longDate, weekdaysLabel } from '../lib/dates';
import type { Habit } from '../lib/types';
import { WeekdayPicker } from '../components/habits/WeekdayPicker';
import { ShortcutPanel } from '../components/habits/ShortcutPanel';
import { useHabitAction, useHabits } from '../hooks/useHabits';
import { useSession } from '../hooks/useSession';

export function HabitsPage() {
  const habits = useHabits();
  const action = useHabitAction();
  const active = (habits.data ?? []).filter((h) => !h.archived_on);
  const archived = (habits.data ?? []).filter((h) => h.archived_on);

  const move = (index: number, delta: number) => {
    const a = active[index];
    const b = active[index + delta];
    if (!a || !b) return;
    // Swap positions; make them distinct if both have the same value
    const aOrder = a.sort_order === b.sort_order ? b.sort_order + delta : b.sort_order;
    action.mutate({ type: 'update', id: a.id, body: { sort_order: aOrder } });
    action.mutate({ type: 'update', id: b.id, body: { sort_order: a.sort_order } });
  };

  return (
    <>
      <div className="page-head week-head-bar">
        <h1>Gewohnheiten</h1>
        <a className="button" href={`${import.meta.env.VITE_API_BASE_URL ?? '/api'}/v1/export.csv`} download>
          Als CSV exportieren
        </a>
      </div>
      <NewHabitForm />

      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      {habits.isPending && <p>Lädt …</p>}
      {habits.isError && <p role="alert" className="error">{errorText(habits.error)}</p>}

      {active.length > 0 && (
        <section aria-labelledby="active-heading">
          <h2 id="active-heading">Aktiv</h2>
          <ul className="habit-list">
            {active.map((habit, i) => (
              <HabitItem
                key={habit.id}
                habit={habit}
                onUp={i > 0 ? () => move(i, -1) : undefined}
                onDown={i < active.length - 1 ? () => move(i, 1) : undefined}
              />
            ))}
          </ul>
        </section>
      )}

      {archived.length > 0 && (
        <details className="archived">
          <summary>Archiviert ({archived.length})</summary>
          <ul className="habit-list">
            {archived.map((habit) => (
              <li key={habit.id} className="habit-item">
                <div className="habit-summary">
                  <span className="habit-title">{habit.name}</span>
                  <span className="subtle">archiviert am {longDate(habit.archived_on!)}</span>
                </div>
                <div className="actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => action.mutate({ type: 'unarchive', id: habit.id })}
                  >
                    Wieder aktivieren
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="subtle version">{APP_NAME} {__APP_VERSION__}</p>
    </>
  );
}

function NewHabitForm() {
  const { today } = useSession();
  const action = useHabitAction();
  const [name, setName] = useState('');
  const [cue, setCue] = useState('');
  const [weekdays, setWeekdays] = useState(127);
  const [startOn, setStartOn] = useState(today);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!weekdays) return;
    action.mutate(
      { type: 'create', body: { name, cue: cue || null, weekdays, start_on: startOn } },
      {
        onSuccess: () => {
          setName('');
          setCue('');
          setWeekdays(127);
        },
      },
    );
  };

  return (
    <form className="card habit-form" onSubmit={submit} aria-labelledby="new-heading">
      <h2 id="new-heading">Neue Gewohnheit</h2>
      <label className="field">
        <span>Name</span>
        <input required maxLength={120} value={name} placeholder="10 Minuten lesen" onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="field">
        <span>Wann oder wo (optional)</span>
        <input maxLength={200} value={cue} placeholder="nach dem Frühstück" onChange={(e) => setCue(e.target.value)} />
      </label>
      <WeekdayPicker value={weekdays} onChange={setWeekdays} />
      <label className="field">
        <span>Beginnt am</span>
        <input type="date" required value={startOn} onChange={(e) => setStartOn(e.target.value)} />
      </label>
      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      <button type="submit" className="button primary" disabled={action.isPending || !weekdays}>
        Anlegen
      </button>
    </form>
  );
}

function HabitItem({ habit, onUp, onDown }: { habit: Habit; onUp?: () => void; onDown?: () => void }) {
  const { today } = useSession();
  const action = useHabitAction();
  const [editing, setEditing] = useState(false);
  const [shortcut, setShortcut] = useState(false);
  const [name, setName] = useState(habit.name);
  const [cue, setCue] = useState(habit.cue ?? '');
  const [weekdays, setWeekdays] = useState(habit.weekdays);
  const [validFrom, setValidFrom] = useState(today);

  const startEdit = () => {
    setName(habit.name);
    setCue(habit.cue ?? '');
    setWeekdays(habit.weekdays);
    setValidFrom(today);
    setEditing(true);
  };

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!weekdays) return;
    try {
      if (name !== habit.name || (cue || null) !== habit.cue) {
        await action.mutateAsync({ type: 'update', id: habit.id, body: { name, cue: cue || null } });
      }
      if (weekdays !== habit.weekdays) {
        await action.mutateAsync({ type: 'schedule', id: habit.id, body: { weekdays, valid_from: validFrom } });
      }
      setEditing(false);
    } catch {
      // action.error shows the message
    }
  };

  if (editing) {
    return (
      <li className="habit-item">
        <form className="habit-form" onSubmit={save} aria-label={`${habit.name} bearbeiten`}>
          <label className="field">
            <span>Name</span>
            <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span>Wann oder wo (optional)</span>
            <input maxLength={200} value={cue} onChange={(e) => setCue(e.target.value)} />
          </label>
          <WeekdayPicker value={weekdays} onChange={setWeekdays} />
          {weekdays !== habit.weekdays && (
            <label className="field">
              <span>Neuer Plan gilt ab</span>
              <input type="date" required value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
              <small className="subtle">Frühere Tage behalten ihren alten Plan.</small>
            </label>
          )}
          {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
          <div className="actions">
            <button type="submit" className="button primary" disabled={action.isPending || !weekdays}>Speichern</button>
            <button type="button" className="button" onClick={() => setEditing(false)}>Abbrechen</button>
          </div>
        </form>
      </li>
    );
  }

  return (
    <li className="habit-item">
      <div className="habit-summary">
        <span className="habit-title">{habit.name}</span>
        <span className="subtle">
          {weekdaysLabel(habit.weekdays)}
          {habit.cue && <> · {habit.cue}</>}
        </span>
      </div>
      <div className="actions">
        <button type="button" className="button icon" disabled={!onUp} onClick={onUp} aria-label={`${habit.name} nach oben`}>↑</button>
        <button type="button" className="button icon" disabled={!onDown} onClick={onDown} aria-label={`${habit.name} nach unten`}>↓</button>
        <button type="button" className="button" onClick={startEdit}>Bearbeiten</button>
        <button type="button" className="button" aria-expanded={shortcut} onClick={() => setShortcut(!shortcut)}>
          Kurzbefehl
        </button>
        <button
          type="button"
          className="button"
          onClick={() => action.mutate({ type: 'archive', id: habit.id })}
          aria-label={`${habit.name} archivieren`}
        >
          Archivieren
        </button>
      </div>
      {shortcut && <ShortcutPanel habit={habit} />}
    </li>
  );
}
