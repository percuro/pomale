import { useState, type FormEvent } from 'react';
import { useErrorText, useI18n } from '../../i18n/context';
import { useGroupAction, usePauses } from '../../hooks/useGroups';
import { useSession } from '../../hooks/useSession';
import type { Habit } from '../../lib/types';

/** Holidays and sick days: not due, so they never lower the quota. */
export function PausesSection({ habits }: { habits: Habit[] }) {
  const { today } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const pauses = usePauses();
  const action = useGroupAction();
  const [habitId, setHabitId] = useState<number | null>(null);
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [reason, setReason] = useState('');
  const names = new Map(habits.map((h) => [h.id, h.name]));

  const add = (event: FormEvent) => {
    event.preventDefault();
    action.mutate(
      { type: 'createPause', body: { habit_id: habitId, start_on: from, end_on: to, reason: reason || null } },
      { onSuccess: () => setReason('') },
    );
  };

  return (
    <section aria-labelledby="pauses-heading" className="settings-section">
      <h2 id="pauses-heading">{t('pauses.title')}</h2>
      <p className="subtle">{t('pauses.intro')}</p>
      <form className="card habit-form" onSubmit={add} aria-labelledby="pauses-heading">
        <label className="field">
          <span>{t('pauses.for')}</span>
          <select value={habitId ?? ''} onChange={(e) => setHabitId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">{t('pauses.all')}</option>
            {habits.map((habit) => (
              <option key={habit.id} value={habit.id}>
                {habit.name}
              </option>
            ))}
          </select>
        </label>
        <div className="field-row">
          <label className="field">
            <span>{t('pauses.from')}</span>
            <input type="date" required value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label className="field">
            <span>{t('pauses.to')}</span>
            <input type="date" required min={from} value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <label className="field">
          <span>{t('pauses.reason')}</span>
          <input maxLength={80} value={reason} placeholder={t('pauses.reasonPlaceholder')} onChange={(e) => setReason(e.target.value)} />
        </label>
        {action.isError && <p role="alert" className="error">{errorText(action.error)}</p>}
        <button type="submit" className="button primary" disabled={action.isPending}>
          {t('pauses.add')}
        </button>
      </form>
      {pauses.isSuccess && pauses.data.length === 0 && <p className="subtle">{t('pauses.empty')}</p>}
      {pauses.data && pauses.data.length > 0 && (
        <ul className="habit-list">
          {pauses.data.map((pause) => {
            const range = format.dateRange(pause.start_on, pause.end_on);
            return (
              <li key={pause.id} className="habit-item">
                <div className="habit-summary">
                  <span className="habit-title">{range}</span>
                  <span className="subtle">
                    {pause.habit_id === null ? t('pauses.all') : (names.get(pause.habit_id) ?? '…')}
                    {pause.reason && <> · {pause.reason}</>}
                  </span>
                </div>
                <button
                  type="button"
                  className="button"
                  aria-label={t('pauses.deleteLabel', { range })}
                  onClick={() => action.mutate({ type: 'deletePause', id: pause.id })}
                >
                  {t('pauses.delete')}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
