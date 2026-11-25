import { useState, type CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { NoteDialog } from '../components/days/NoteDialog';
import { addDays, weekStart } from '../lib/dates';
import { byGroup, colorStyle } from '../lib/habit-style';
import { StateIcon } from '../components/days/StateIcon';
import { MinusIcon, PencilIcon, PlusIcon, UndoIcon } from '../components/Icons';
import { useErrorText, useI18n } from '../i18n/context';
import type { Day, HabitDays } from '../lib/types';
import { setDay, useDays } from '../hooks/useDays';
import { useSession } from '../hooks/useSession';

interface Row {
  habit: HabitDays;
  day: Day;
}

type Section = 'main' | 'doneThisWeek' | 'paused' | 'unplanned';

/** Where a habit appears today. Rows never jump while checking off: a weekly goal
 *  reached today stays in the main list; only on later days it moves to "done this week". */
function sectionOf({ habit, day }: Row): Section {
  if (day.paused && !day.done && !(day.value && day.value > 0)) return 'paused';
  if (habit.goal_type === 'weekly_count' && day.goal_type === 'weekly_count') {
    const week = habit.week;
    if (!day.planned) return 'unplanned';
    if (week && week.target > 0 && week.done >= week.target && !day.done) return 'doneThisWeek';
    return 'main';
  }
  return day.planned ? 'main' : 'unplanned';
}

export function TodayPage() {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  // Load the whole week: shares the offline cache with the week view, keeps working
  // across midnight while offline, and weekly goals need their week
  const start = weekStart(today);
  const days = useDays(start, addDays(start, 6));
  const [noteFor, setNoteFor] = useState<Row | null>(null);

  if (days.isPending) return <p>{t('app.loading')}</p>;
  if (!days.data) {
    return (
      <p role="alert" className="error">
        {days.error instanceof TypeError ? t('today.offlineNoData') : errorText(days.error)}
      </p>
    );
  }

  const rows = days.data.habits
    .filter((habit) => !habit.archived)
    .map((habit) => ({ habit, day: habit.days.find((d) => d.date === today) }))
    .filter((row): row is Row => Boolean(row.day));
  const bySection = (section: Section) => rows.filter((row) => sectionOf(row) === section);
  const main = bySection('main');
  const doneCount = main.filter((row) => row.day.done).length;
  const groups = byGroup(
    main.map((row) => ({ ...row, group_id: row.habit.group_id })),
    days.data.groups,
  );
  const showGroupNames = groups.some((group) => group.id !== null);

  const rowProps = { onNote: setNoteFor };

  return (
    <>
      <div className="page-head today-head">
        <div>
          <h1>{t('today.title')}</h1>
          <p className="subtle">
            {format.longDate(today)}
            {main.length > 0 && <> · {t('today.progress', { done: doneCount, total: main.length })}</>}
          </p>
        </div>
        {/* The share that is done as a ring; the sentence next to it says the same */}
        {main.length > 0 && (
          <div className="ring" style={{ '--p': Math.round((doneCount / main.length) * 100) } as CSSProperties} aria-hidden="true">
            <span>{doneCount}/{main.length}</span>
          </div>
        )}
      </div>

      {rows.length === 0 && (
        <p className="empty">
          {t('today.empty')} <Link to="/habits">{t('today.createHabit')}</Link>
        </p>
      )}

      {groups.map((group) => (
        <section key={group.id ?? 'none'} className="today-group" aria-label={group.name ?? t('today.otherGroup')}>
          {showGroupNames && <h2 className="group-title">{group.name ?? t('today.otherGroup')}</h2>}
          <ul className="today-list">
            {group.items.map((row) => (
              <TodayRow key={row.habit.id} {...row} {...rowProps} />
            ))}
          </ul>
        </section>
      ))}

      {(['doneThisWeek', 'unplanned', 'paused'] as const).map((section) => {
        const items = bySection(section);
        if (!items.length) return null;
        const title = {
          doneThisWeek: t('today.doneThisWeek', { count: items.length }),
          unplanned: t('today.unplanned', { count: items.length }),
          paused: t('today.pausedSection', { count: items.length }),
        }[section];
        return (
          <details className="unplanned" key={section}>
            <summary>{title}</summary>
            <ul className="today-list">
              {items.map((row) => (
                <TodayRow key={row.habit.id} {...row} {...rowProps} />
              ))}
            </ul>
          </details>
        );
      })}

      {noteFor && (
        <NoteDialog
          habitId={noteFor.habit.id}
          habitName={noteFor.habit.name}
          date={today}
          note={noteFor.day.note}
          onClose={() => setNoteFor(null)}
        />
      )}
    </>
  );
}

function TodayRow({ habit, day, onNote }: Row & { onNote: (row: Row) => void }) {
  const t = useI18n().t;
  const status = (
    <span className="today-status">
      {t(`state.${day.state}`)}
      {day.conflict ? (
        <span className="pending"> · {t('today.conflict')}</span>
      ) : (
        day.pending && <span className="pending"> · {t('today.pending')}</span>
      )}
    </span>
  );
  const noteButton = (
    <button
      type="button"
      className={`icon-button note-button${day.note ? ' has-note' : ''}`}
      aria-label={t('today.noteLabel', { name: habit.name }) + (day.note ? ` (${t('today.hasNote')})` : '')}
      title={day.note ?? t('today.note')}
      onClick={() => onNote({ habit, day })}
    >
      <PencilIcon />
    </button>
  );

  if (day.goal_type === 'quantity') {
    const value = day.value ?? 0;
    const target = day.target ?? 1;
    const amount = habit.unit
      ? t('today.amountUnit', { value, target, unit: habit.unit })
      : t('today.amount', { value, target });
    const set = (next: number) => setDay(habit.id, day.date, { value: Math.max(0, Math.min(9999, next)) }, day.version);
    return (
      <li className={`today-row quantity state-${day.state}`} style={colorStyle(habit.color)}>
        <button
          type="button"
          className="today-main"
          aria-pressed={day.done}
          onClick={() => {
            if (value < target) set(target);
          }}
        >
          <StateIcon state={day.state} value={value} target={target} />
          <span className="today-text">
            <span className="today-name">{habit.name}</span>
            {habit.cue && <span className="today-cue">{habit.cue}</span>}
            <span className="today-amount">{amount}</span>
            {status}
            {/* The name of the button contains what is visible, then says what a tap does */}
            <span className="sr-only">{t('today.reach', { name: habit.name })}</span>
          </span>
        </button>
        <div className="stepper" role="group" aria-label={amount}>
          <button
            type="button"
            className="button icon"
            aria-label={t('today.less', { name: habit.name })}
            disabled={value <= 0}
            onClick={() => set(value - 1)}
          >
            <MinusIcon />
          </button>
          <span className="stepper-value" aria-live="polite">
            {value}
          </span>
          <button type="button" className="button icon" aria-label={t('today.more', { name: habit.name })} onClick={() => set(value + 1)}>
            <PlusIcon />
          </button>
        </div>
        {noteButton}
      </li>
    );
  }

  return (
    <li className={`today-row state-${day.state}`} style={colorStyle(habit.color)}>
      <button
        type="button"
        className="today-main"
        aria-pressed={day.done}
        onClick={() => {
          if (!day.done) setDay(habit.id, day.date, true, day.version);
        }}
      >
        <StateIcon state={day.state} />
        <span className="today-text">
          <span className="today-name">{habit.name}</span>
          {habit.cue && <span className="today-cue">{habit.cue}</span>}
          {habit.week && day.goal_type === 'weekly_count' && (
            <span className="today-amount">{t('today.weekProgress', { done: habit.week.done, target: habit.week.target })}</span>
          )}
          {status}
        </span>
      </button>
      {/* Space stays reserved so the row does not jump when checking off */}
      <button
        type="button"
        className="icon-button undo"
        hidden={!day.done}
        aria-label={t('today.undoLabel', { name: habit.name })}
        title={t('today.undo')}
        onClick={() => setDay(habit.id, day.date, false, day.version)}
      >
        <UndoIcon />
      </button>
      {noteButton}
    </li>
  );
}
