import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { longDate } from '../../lib/dates';
import { syncEngine } from '../../lib/sync-engine';
import type { DaysResponse } from '../../lib/types';
import { DAYS_KEY } from '../../hooks/useDays';
import { useOnline } from '../../hooks/useOnline';
import { useSync } from '../../hooks/useSync';

function stateText(done: boolean) {
  return done ? 'erledigt' : 'offen';
}

function formatTime(iso: string | null) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return ` (geändert ${date.toLocaleString('de-AT', { dateStyle: 'short', timeStyle: 'short' })})`;
}

/** Online changes usually confirm within milliseconds; only mention them if they hang. */
const STUCK_AFTER_MS = 3000;

/** Hints about connectivity, pending changes and conflicts. */
export function SyncStatus() {
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
          {!online && 'Offline. '}
          {pending.length > 0
            ? `${pending.length} ${pending.length === 1 ? 'Änderung wartet' : 'Änderungen warten'} auf Übertragung.`
            : 'Änderungen werden auf diesem Gerät gespeichert und gesendet, sobald wieder Verbindung besteht.'}
          {online && pending.length > 0 && (
            <button type="button" className="link-button" onClick={() => void syncEngine.flush()}>
              Jetzt senden
            </button>
          )}
        </p>
      )}
      {lastError && <p className="error" role="alert">Nicht gespeichert: {lastError.message}</p>}
      {conflicts.map((op) => (
        <section
          key={op.op_id}
          className="card conflict"
          role="alertdialog"
          aria-labelledby={`conflict-${op.op_id}`}
          aria-describedby={`conflict-desc-${op.op_id}`}
        >
          <h2 id={`conflict-${op.op_id}`}>Abweichende Änderung</h2>
          <p id={`conflict-desc-${op.op_id}`}>
            <strong>{names.get(op.habit_id) ?? `Gewohnheit ${op.habit_id}`}</strong>, {longDate(op.date)}: Dieser
            Eintrag wurde auf einem anderen Gerät geändert, während diese Änderung noch nicht übertragen war.
          </p>
          <dl className="conflict-states">
            <dt>Auf diesem Gerät</dt>
            <dd>{stateText(op.done)}</dd>
            <dt>Auf dem Server</dt>
            <dd>
              {stateText(op.conflict!.done)}
              {formatTime(op.conflict!.updated_at)}
            </dd>
          </dl>
          <div className="actions">
            <button type="button" className="button primary" onClick={() => void syncEngine.resolve(op.op_id, 'device')}>
              Gerätestand übernehmen
            </button>
            <button type="button" className="button" onClick={() => void syncEngine.resolve(op.op_id, 'server')}>
              Serverstand behalten
            </button>
          </div>
        </section>
      ))}
    </>
  );
}
