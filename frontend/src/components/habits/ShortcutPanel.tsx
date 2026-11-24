import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch, errorText } from '../../lib/api';
import type { Habit } from '../../lib/types';

interface TokenRead {
  id: number;
  label: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

interface TokenCreated extends TokenRead {
  token: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

function formatUtc(iso: string | null): string {
  if (!iso) return 'nie';
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);
  return date.toLocaleString('de-AT', { dateStyle: 'short', timeStyle: 'short' });
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="copy-field">
      <span className="copy-label">{label}</span>
      <code>{value}</code>
      <button
        type="button"
        className="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
          } catch {
            setCopied(false);
          }
        }}
      >
        {copied ? 'Kopiert' : 'Kopieren'}
      </button>
    </div>
  );
}

/** Create and revoke keys for the favourite-habit shortcut. */
export function ShortcutPanel({ habit }: { habit: Habit }) {
  const queryClient = useQueryClient();
  const key = ['shortcut-tokens', habit.id];
  const tokens = useQuery({
    queryKey: key,
    queryFn: () => apiFetch<TokenRead[]>(`/v1/habits/${habit.id}/shortcut-tokens`),
  });
  const [label, setLabel] = useState('iPhone');
  const [created, setCreated] = useState<TokenCreated | null>(null);
  const create = useMutation({
    mutationFn: () =>
      apiFetch<TokenCreated>(`/v1/habits/${habit.id}/shortcut-tokens`, {
        method: 'POST',
        body: JSON.stringify({ label }),
      }),
    onSuccess: (token) => {
      setCreated(token);
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) =>
      apiFetch<void>(`/v1/habits/${habit.id}/shortcut-tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const url = `${window.location.origin}${API_BASE_URL}/v1/habits/${habit.id}/days/today`;
  const active = (tokens.data ?? []).filter((token) => !token.revoked_at);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };

  return (
    <section className="shortcut-panel" aria-label={`Kurzbefehl für ${habit.name}`}>
      <h3>Kurzbefehl „{habit.name} abhaken“</h3>
      <p className="subtle">
        Der Schlüssel darf nur diese Gewohnheit für heute auf erledigt setzen. Er wird nur jetzt einmal angezeigt –
        nicht in Screenshots, Notizen oder Nachrichten ablegen.
      </p>

      {created ? (
        <div className="card created-token" role="status">
          <p><strong>Schlüssel „{created.label}“ angelegt.</strong> In Kurzbefehle → „Inhalte von URL abrufen“ eintragen:</p>
          <CopyField label="URL" value={url} />
          <CopyField label="Methode" value="PUT" />
          <CopyField label="Header Authorization" value={`Bearer ${created.token}`} />
          <CopyField label="JSON-Feld done (Boolesch)" value="true" />
          <p className="subtle">
            Danach „Wörterbuchwert für message abrufen“ und „Ergebnis anzeigen“. Anleitung: deploy/IPHONE.md.
          </p>
          <button type="button" className="button" onClick={() => setCreated(null)}>
            Fertig, Schlüssel ausblenden
          </button>
        </div>
      ) : (
        <form className="actions" onSubmit={submit}>
          <label className="field inline">
            <span>Gerät</span>
            <input value={label} maxLength={80} required onChange={(e) => setLabel(e.target.value)} />
          </label>
          <button type="submit" className="button primary" disabled={create.isPending}>
            Schlüssel anlegen
          </button>
        </form>
      )}
      {create.isError && <p className="error" role="alert">{errorText(create.error)}</p>}

      {active.length > 0 && (
        <ul className="token-list">
          {active.map((token) => (
            <li key={token.id}>
              <span>
                <strong>{token.label}</strong>
                <span className="subtle"> · angelegt {formatUtc(token.created_at)} · zuletzt benutzt {formatUtc(token.last_used_at)}</span>
              </span>
              <button
                type="button"
                className="button"
                onClick={() => revoke.mutate(token.id)}
                aria-label={`Schlüssel ${token.label} widerrufen`}
              >
                Widerrufen
              </button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <p className="error" role="alert">{errorText(revoke.error)}</p>}
    </section>
  );
}
