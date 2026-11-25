import { APP_NAME } from '../app/brand';
import { useState, type FormEvent } from 'react';
import { useErrorText, useI18n } from '../i18n/context';
import type { Habit } from '../lib/types';
import { WeekdayPicker } from '../components/habits/WeekdayPicker';
import { ShortcutPanel } from '../components/habits/ShortcutPanel';
import { useHabitAction, useHabits } from '../hooks/useHabits';
import { useSession } from '../hooks/useSession';

export function HabitsPage() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
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
      <div className="page-head">
        <h1>{t('habits.title')}</h1>
      </div>
      <NewHabitForm />

      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      {habits.isPending && <p>{t('app.loading')}</p>}
      {habits.isError && <p role="alert" className="error">{errorText(habits.error)}</p>}

      {active.length > 0 && (
        <section aria-labelledby="active-heading">
          <h2 id="active-heading">{t('habits.active')}</h2>
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
          <summary>{t('habits.archivedCount', { count: archived.length })}</summary>
          <ul className="habit-list">
            {archived.map((habit) => (
              <li key={habit.id} className="habit-item">
                <div className="habit-summary">
                  <span className="habit-title">{habit.name}</span>
                  <span className="subtle">{t('habits.archivedOn', { date: format.longDate(habit.archived_on!) })}</span>
                </div>
                <div className="actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => action.mutate({ type: 'unarchive', id: habit.id })}
                  >
                    {t('habits.reactivate')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="subtle version">{t('app.version', { name: APP_NAME, version: __APP_VERSION__ })}</p>
    </>
  );
}

function NewHabitForm() {
  const { today } = useSession();
  const t = useI18n().t;
  const errorText = useErrorText();
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
      <h2 id="new-heading">{t('habits.new')}</h2>
      <label className="field">
        <span>{t('habits.name')}</span>
        <input
          required
          maxLength={120}
          value={name}
          placeholder={t('habits.namePlaceholder')}
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label className="field">
        <span>{t('habits.cue')}</span>
        <input
          maxLength={200}
          value={cue}
          placeholder={t('habits.cuePlaceholder')}
          onChange={(e) => setCue(e.target.value)}
        />
      </label>
      <WeekdayPicker value={weekdays} onChange={setWeekdays} />
      <label className="field">
        <span>{t('habits.startsOn')}</span>
        <input type="date" required value={startOn} onChange={(e) => setStartOn(e.target.value)} />
      </label>
      {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
      <button type="submit" className="button primary" disabled={action.isPending || !weekdays}>
        {t('habits.create')}
      </button>
    </form>
  );
}

function HabitItem({ habit, onUp, onDown }: { habit: Habit; onUp?: () => void; onDown?: () => void }) {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
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
        <form className="habit-form" onSubmit={save} aria-label={t('habits.editLabel', { name: habit.name })}>
          <label className="field">
            <span>{t('habits.name')}</span>
            <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span>{t('habits.cue')}</span>
            <input maxLength={200} value={cue} onChange={(e) => setCue(e.target.value)} />
          </label>
          <WeekdayPicker value={weekdays} onChange={setWeekdays} />
          {weekdays !== habit.weekdays && (
            <label className="field">
              <span>{t('habits.newPlanFrom')}</span>
              <input type="date" required value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
              <small className="subtle">{t('habits.newPlanHint')}</small>
            </label>
          )}
          {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
          <div className="actions">
            <button type="submit" className="button primary" disabled={action.isPending || !weekdays}>
              {t('common.save')}
            </button>
            <button type="button" className="button" onClick={() => setEditing(false)}>
              {t('common.cancel')}
            </button>
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
          {format.weekdays(habit.weekdays)}
          {habit.cue && <> · {habit.cue}</>}
        </span>
      </div>
      <div className="actions">
        <button
          type="button"
          className="button icon"
          disabled={!onUp}
          onClick={onUp}
          aria-label={t('habits.moveUp', { name: habit.name })}
        >
          ↑
        </button>
        <button
          type="button"
          className="button icon"
          disabled={!onDown}
          onClick={onDown}
          aria-label={t('habits.moveDown', { name: habit.name })}
        >
          ↓
        </button>
        <button type="button" className="button" onClick={startEdit}>
          {t('habits.edit')}
        </button>
        <button type="button" className="button" aria-expanded={shortcut} onClick={() => setShortcut(!shortcut)}>
          {t('habits.shortcut')}
        </button>
        <button
          type="button"
          className="button"
          onClick={() => action.mutate({ type: 'archive', id: habit.id })}
          aria-label={t('habits.archiveLabel', { name: habit.name })}
        >
          {t('habits.archive')}
        </button>
      </div>
      {shortcut && <ShortcutPanel habit={habit} />}
    </li>
  );
}
