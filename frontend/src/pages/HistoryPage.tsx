import { useState } from 'react';
import { Link } from 'react-router-dom';
import { OnlineOnly } from '../components/common/OnlineOnly';
import { addDays, weekStart } from '../lib/dates';
import { colorStyle } from '../lib/habit-style';
import { STATE_ICON } from '../lib/states';
import { useErrorText, useI18n } from '../i18n/context';
import type { HistoryDay, HistoryHabit, HistoryWeek, Quota } from '../lib/types';
import { useHabits } from '../hooks/useHabits';
import { useHistory } from '../hooks/useHistory';
import { useSession } from '../hooks/useSession';

/** One request covers a year of weeks: quota per period, trend and calendar all come from it. */
const WEEKS = 52;
const PERIODS = [4, 12, 26, 52];

export function HistoryPage() {
  const t = useI18n().t;
  const habits = useHabits();
  const active = (habits.data ?? []).filter((h) => !h.archived_on);
  const archived = (habits.data ?? []).filter((h) => h.archived_on);
  const [habitId, setHabitId] = useState<number | null>(null);
  const selected = habitId ?? active[0]?.id ?? archived[0]?.id ?? null;

  return (
    <>
      <div className="page-head">
        <h1>{t('history.title')}</h1>
        <p className="subtle">{t('history.intro')}</p>
      </div>
      <OnlineOnly>
        {habits.isSuccess && selected === null && (
          <p className="empty">
            {t('history.empty')} <Link to="/habits">{t('today.createHabit')}</Link>
          </p>
        )}
        {selected !== null && (
          <>
            <label className="field history-select">
              <span>{t('history.habit')}</span>
              <select value={selected} onChange={(e) => setHabitId(Number(e.target.value))}>
                {[...active, ...archived].map((habit) => (
                  <option key={habit.id} value={habit.id}>
                    {habit.name}
                  </option>
                ))}
              </select>
            </label>
            <HabitHistory habitId={selected} />
          </>
        )}
      </OnlineOnly>
    </>
  );
}

function sum(weeks: HistoryWeek[]): Quota {
  return weeks.reduce((total, w) => ({ done: total.done + w.done, due: total.due + w.due }), { done: 0, due: 0 });
}

function HabitHistory({ habitId }: { habitId: number }) {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const from = addDays(weekStart(today), -7 * (WEEKS - 1));
  const history = useHistory(from, today, habitId);
  const habit = history.data?.habits[0];

  if (history.isPending) return <p>{t('app.loading')}</p>;
  if (history.isError) return <p role="alert" className="error">{errorText(history.error)}</p>;
  if (!habit) return null;

  const quotaText = (quota: Quota) =>
    quota.due > 0
      ? `${t('history.quota', { done: quota.done, due: quota.due })} (${format.percent(quota.done / quota.due)})`
      : t('history.nothingDue');

  return (
    <div className="history" style={colorStyle(habit.color)}>
      <section aria-labelledby="periods-heading" className="card">
        <h2 id="periods-heading">{t('history.periods')}</h2>
        <dl className="period-list">
          {PERIODS.map((count) => (
            <div key={count}>
              <dt>{t('history.lastWeeks', { count })}</dt>
              <dd>{quotaText(sum(habit.weeks.slice(-count)))}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Trend weeks={habit.weeks.slice(-12)} />
      <Calendar habit={habit} from={from} />
    </div>
  );
}

function Trend({ weeks }: { weeks: HistoryWeek[] }) {
  const { t, format } = useI18n();
  const barWidth = 20;
  const gap = 6;
  const height = 80;
  return (
    <section aria-labelledby="trend-heading" className="card">
      <h2 id="trend-heading">{t('history.trend')}</h2>
      <svg
        className="trend"
        viewBox={`0 0 ${weeks.length * (barWidth + gap)} ${height + 2}`}
        role="img"
        aria-label={t('history.trendLabel')}
        preserveAspectRatio="none"
      >
        {weeks.map((week, i) => {
          const ratio = week.due > 0 ? week.done / week.due : 0;
          const barHeight = Math.max(week.due > 0 ? 2 : 0, ratio * height);
          return (
            <g key={week.week_start}>
              <title>{t('history.bar', { date: format.shortDate(week.week_start), done: week.done, due: week.due })}</title>
              <rect className="trend-track" x={i * (barWidth + gap)} y={0} width={barWidth} height={height} rx={4} />
              <rect
                className="trend-bar"
                x={i * (barWidth + gap)}
                y={height - barHeight}
                width={barWidth}
                height={barHeight}
                rx={4}
              />
            </g>
          );
        })}
      </svg>
      <details>
        <summary>{t('history.trendTable')}</summary>
        <table className="trend-table">
          <thead>
            <tr>
              <th scope="col">{t('history.week')}</th>
              <th scope="col">{t('history.done')}</th>
              <th scope="col">{t('history.due')}</th>
            </tr>
          </thead>
          <tbody>
            {weeks.map((week) => (
              <tr key={week.week_start}>
                <th scope="row">{format.dateRange(week.week_start, addDays(week.week_start, 6))}</th>
                <td>{week.done}</td>
                <td>{week.due}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function monthStart(iso: string): string {
  return `${iso.slice(0, 7)}-01`;
}

function addMonths(iso: string, months: number): string {
  const [y, m] = iso.split('-').map(Number);
  const index = y * 12 + (m - 1) + months;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}-01`;
}

/** Month calendar as a real table: every cell names its state, so it is its own text alternative. */
function Calendar({ habit, from }: { habit: HistoryHabit; from: string }) {
  const { today } = useSession();
  const { t, format } = useI18n();
  const [month, setMonth] = useState(monthStart(today));
  const [chosen, setChosen] = useState<HistoryDay | null>(null);
  const byDate = new Map((habit.days ?? []).map((day) => [day.date, day]));
  const first = month;
  const last = addDays(addMonths(month, 1), -1);
  const gridStart = weekStart(first);
  const weeks: string[][] = [];
  for (let day = gridStart; day <= last; day = addDays(day, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(day, i)));
  }
  const canGoBack = addMonths(month, -1) >= monthStart(from);
  const canGoForward = addMonths(month, 1) <= monthStart(today);

  const label = (day: HistoryDay) => {
    let text = t('history.dayLabel', { date: format.longDate(day.date), state: t(`state.${day.state}`) });
    if (habit.goal_type === 'quantity' && day.value !== null && day.state !== 'future') {
      text += `, ${t('history.amount', { value: day.value, target: habit.target ?? 1 })}`;
    }
    if (day.note) text += `, ${t('today.hasNote')}`;
    return text;
  };

  return (
    <section aria-labelledby="calendar-heading" className="card">
      <div className="calendar-head">
        <h2 id="calendar-heading">
          {t('history.calendar')}: {format.monthYear(month)}
        </h2>
        <div className="week-nav">
          <button type="button" className="button" disabled={!canGoBack} onClick={() => setMonth(addMonths(month, -1))}>
            {t('history.previousMonth')}
          </button>
          <button type="button" className="button" disabled={!canGoForward} onClick={() => setMonth(addMonths(month, 1))}>
            {t('history.nextMonth')}
          </button>
        </div>
      </div>
      <table className="calendar">
        <caption className="visually-hidden">
          {habit.name}, {format.monthYear(month)}
        </caption>
        <thead>
          <tr>
            {[0, 1, 2, 3, 4, 5, 6].map((i) => (
              <th scope="col" key={i} abbr={format.weekdayLong(i)}>
                {format.weekdayShort(i)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0]}>
              {week.map((date) => {
                const day = byDate.get(date);
                if (date < first || date > last || !day) {
                  return <td key={date} className="calendar-empty" aria-hidden={date < first || date > last} />;
                }
                return (
                  <td key={date}>
                    <button
                      type="button"
                      className={`calendar-day state-${day.state}${day.note ? ' has-note' : ''}${date === today ? ' is-today' : ''}`}
                      aria-label={label(day)}
                      aria-pressed={chosen?.date === date}
                      onClick={() => setChosen(day)}
                    >
                      <span className="calendar-date" aria-hidden="true">
                        {Number(date.slice(8))}
                      </span>
                      <span aria-hidden="true">
                        {habit.goal_type === 'quantity' && (day.value ?? 0) > 0 ? day.value : STATE_ICON[day.state]}
                      </span>
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="subtle" aria-live="polite">
        {chosen ? (
          <>
            <strong>{label(chosen)}</strong>
            {chosen.note && (
              <>
                <br />
                {t('history.note', { note: chosen.note })}
              </>
            )}
          </>
        ) : (
          t('history.chooseDay')
        )}
      </p>
    </section>
  );
}
