import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { codeMessage } from '../../i18n/core';
import { useI18n } from '../../i18n/context';
import { syncEngine } from '../../lib/sync-engine';
import type { DaysResponse } from '../../lib/types';
import { DAYS_KEY } from '../../hooks/useDays';
import { useOnline } from '../../hooks/useOnline';
import { useSync } from '../../hooks/useSync';

/** Online changes usually confirm within milliseconds; only mention them if they hang. */
const STUCK_AFTER_MS = 3000;

/** Hints about connectivity, pending changes and conflicts. */
export function SyncStatus() {
  const { t, format } = useI18n();
  const online = useOnline();
  const { ops, lastError } = useSync();
  const queryClient = useQueryClient();
  const pending = ops.filter((op) => !op.conflict);
  const conflicts = ops.filter((op) => op.conflict);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (pending.length === 0) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [pending.length]);
  // Avoid a banner flashing above the list (and shifting it) on every tap
  const stuck = pending.some((op) => now - op.created_at > STUCK_AFTER_MS);

  const names = new Map<number, string>();
  for (const [, data] of queryClient.getQueriesData<DaysResponse>({ queryKey: DAYS_KEY })) {
    data?.habits.forEach((habit) => names.set(habit.id, habit.name));
  }

  return (
    <>
      {(!online || stuck) && (
        <p className="sync-banner" role="status">
          <span aria-hidden="true">{online ? '⇅' : '⚠'}</span>{' '}
          {!online && `${t('sync.offline')} `}
          {pending.length > 0 ? t('sync.waiting', { count: pending.length }) : t('sync.storedLocally')}
          {online && pending.length > 0 && (
            <button type="button" className="link-button" onClick={() => void syncEngine.flush()}>
              {t('sync.sendNow')}
            </button>
          )}
        </p>
      )}
      {lastError && (
        <p className="error" role="alert">
          {t('sync.notSaved', {
            reason: codeMessage(lastError.code, t) ?? lastError.message,
          })}
        </p>
      )}
      {conflicts.map((op) => (
        <section
          key={op.op_id}
          className="card conflict"
          role="alertdialog"
          aria-labelledby={`conflict-${op.op_id}`}
          aria-describedby={`conflict-desc-${op.op_id}`}
        >
          <h2 id={`conflict-${op.op_id}`}>{t('sync.conflictTitle')}</h2>
          <p id={`conflict-desc-${op.op_id}`}>
            <strong>{names.get(op.habit_id) ?? t('sync.habitFallback', { id: op.habit_id })}</strong>,{' '}
            {format.longDate(op.date)}: {t('sync.conflictText')}
          </p>
          <dl className="conflict-states">
            <dt>{t('sync.thisDevice')}</dt>
            <dd>{op.value !== undefined ? String(op.value) : op.done ? t('sync.done') : t('sync.open')}</dd>
            <dt>{t('sync.server')}</dt>
            <dd>
              {op.value !== undefined
                ? String(op.conflict!.value ?? 0)
                : op.conflict!.done
                  ? t('sync.done')
                  : t('sync.open')}
              {op.conflict!.updated_at && t('sync.changedAt', { time: format.dateTime(op.conflict!.updated_at) })}
            </dd>
          </dl>
          <div className="actions">
            <button type="button" className="button primary" onClick={() => void syncEngine.resolve(op.op_id, 'device')}>
              {t('sync.keepDevice')}
            </button>
            <button type="button" className="button" onClick={() => void syncEngine.resolve(op.op_id, 'server')}>
              {t('sync.keepServer')}
            </button>
          </div>
        </section>
      ))}
    </>
  );
}
