import { useRef, useState, type KeyboardEvent } from 'react';
import { Link } from 'react-router-dom';
import { AmountDialog } from '../components/days/AmountDialog';
import { addDays, weekStart } from '../lib/dates';
import { byGroup, colorStyle } from '../lib/habit-style';
import { StateIcon } from '../components/days/StateIcon';
import { useErrorText, useI18n } from '../i18n/context';
import type { Day, HabitDays } from '../lib/types';
import { setDay, useDays } from '../hooks/useDays';
import { useSession } from '../hooks/useSession';

export function WeekPage() {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const currentWeek = weekStart(today);
  const [start, setStart] = useState(currentWeek);
  const end = addDays(start, 6);
  const days = useDays(start, end);
  const [active, setActive] = useState<[number, number]>([0, 0]);
  const gridRef = useRef<HTMLDivElement>(null);

  const [amountFor, setAmountFor] = useState<{ habit: HabitDays; day: Day } | null>(null);

  const dates = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const sections = byGroup(days.data?.habits ?? [], days.data?.groups ?? []);
  const showGroupNames = sections.some((section) => section.id !== null);
  // Flat order for keyboard navigation across groups
  const habits = sections.flatMap((section) => section.items);

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
    if (day.goal_type === 'quantity') setAmountFor({ habit, day });
    else setDay(habit.id, day.date, !day.done, day.version);
  };

  const quotaText = (habit: HabitDays) => {
    if (habit.goal_type === 'weekly_count' && habit.week && start === currentWeek) {
      return t('week.weekQuota', { done: habit.week.done, target: habit.week.target });
    }
    return habit.quota.due > 0 ? t('week.quota', { done: habit.quota.done, due: habit.quota.due }) : t('week.nothingDue');
  };

  const cellLabel = (habit: HabitDays, day: Day, c: number) => {
    const dayText = `${format.weekdayLong(c)} ${format.shortDate(day.date)}`;
    const state = t(`state.${day.state}`);
    const base =
      day.goal_type === 'quantity' && day.state !== 'future'
        ? t('week.cellValue', { habit: habit.name, day: dayText, value: day.value ?? 0, target: day.target ?? 1, state })
        : t('week.cellLabel', { habit: habit.name, day: dayText, state });
    return (
      base +
      (day.note ? t('week.cellNote') : '') +
      (day.conflict ? t('week.cellConflict') : day.pending ? t('week.cellPending') : '')
    );
  };

  return (
    <>
      <div className="page-head week-head-bar">
        <div>
          <h1>{t('week.title')}</h1>
          <p className="subtle">{format.dateRange(start, end)}</p>
        </div>
        <div className="week-nav" role="group" aria-label={t('week.choose')}>
          <button type="button" className="button" onClick={() => setStart(addDays(start, -7))}>
            {t('week.previous')}
          </button>
          <button
            type="button"
            className="button"
            disabled={start === currentWeek}
            onClick={() => setStart(currentWeek)}
          >
            {t('week.current')}
          </button>
          <button
            type="button"
            className="button"
            disabled={start >= currentWeek}
            onClick={() => setStart(addDays(start, 7))}
          >
            {t('week.next')}
          </button>
        </div>
      </div>

      {days.data?.offline && (
        <p className="subtle" role="status">{t('week.offline')}</p>
      )}
      {days.isPending && <p>{t('app.loading')}</p>}
      {days.isError && !days.data && <p role="alert" className="error">{errorText(days.error)}</p>}
      {days.isSuccess && habits.length === 0 && (
        <p className="empty">
          {t('week.empty')} <Link to="/habits">{t('today.createHabit')}</Link>
        </p>
      )}

      {habits.length > 0 && (
        <div
          className="week-grid"
          role="grid"
          aria-label={t('week.gridLabel', { date: format.longDate(start) })}
          aria-describedby="week-help"
          ref={gridRef}
          onKeyDown={onKeyDown}
        >
          <div role="row" className="week-row week-columns">
            <span role="columnheader" className="week-name">{t('week.habit')}</span>
            {dates.map((date, i) => (
              <span
                role="columnheader"
                key={date}
                className={date === today ? 'week-day is-today' : 'week-day'}
                aria-label={format.longDate(date)}
              >
                {format.weekdayShort(i)}
                <small>{format.shortDate(date)}</small>
              </span>
            ))}
          </div>
          {sections.map((section) => (
            <div role="rowgroup" key={section.id ?? 'none'}>
              {showGroupNames && (
                <div role="row" className="week-group">
                  <span role="rowheader" aria-colspan={8}>
                    {section.name ?? t('week.groupOther')}
                  </span>
                </div>
              )}
              {section.items.map((habit) => {
                const r = habits.indexOf(habit);
                return (
                  <div role="row" className="week-row" key={habit.id} style={colorStyle(habit.color)}>
                    <span role="rowheader" className="week-name">
                      <span className="week-habit">{habit.name}</span>
                      <small className="quota">
                        {quotaText(habit)}
                        {habit.archived && ` · ${t('week.archived')}`}
                      </small>
                    </span>
                    {habit.days.map((day, c) => (
                      <span role="gridcell" key={day.date} className={day.date === today ? 'is-today' : undefined}>
                        <button
                          type="button"
                          data-cell={`${r}-${c}`}
                          className={`cell state-${day.state}${day.pending ? ' is-pending' : ''}${day.conflict ? ' is-conflict' : ''}${day.note ? ' has-note' : ''}`}
                          tabIndex={active[0] === r && active[1] === c ? 0 : -1}
                          aria-pressed={day.state === 'future' || day.goal_type === 'quantity' ? undefined : day.done}
                          aria-haspopup={day.goal_type === 'quantity' && day.state !== 'future' ? 'dialog' : undefined}
                          aria-disabled={day.state === 'future'}
                          aria-label={cellLabel(habit, day, c)}
                          title={
                            (day.pending
                              ? t('week.cellPendingTitle', { state: t(`state.${day.state}`) })
                              : t(`state.${day.state}`)) + (day.note ? ` – ${day.note}` : '')
                          }
                          onFocus={() => setActive([r, c])}
                          onClick={() => toggle(habit, day)}
                        >
                          <StateIcon state={day.state} value={day.value} target={day.target} />
                        </button>
                      </span>
                    ))}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
      <p id="week-help" className="subtle help">
        {t('week.help')}
      </p>
      {amountFor && (
        <AmountDialog
          habitName={amountFor.habit.name}
          date={amountFor.day.date}
          value={amountFor.day.value ?? 0}
          target={amountFor.day.target ?? 1}
          unit={amountFor.habit.unit}
          onSave={(value) => setDay(amountFor.habit.id, amountFor.day.date, { value }, amountFor.day.version)}
          onClose={() => setAmountFor(null)}
        />
      )}
    </>
  );
}
