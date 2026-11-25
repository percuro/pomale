import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import { useErrorText, useI18n, useT } from '../../i18n/context';
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

export function CopyField({ label, value }: { label: string; value: string }) {
  const t = useT();
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
        {copied ? t('common.copied') : t('common.copy')}
      </button>
    </div>
  );
}

/** Create and revoke keys for the favourite-habit shortcut. */
export function ShortcutPanel({ habit }: { habit: Habit }) {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const key = ['shortcut-tokens', habit.id];
  const tokens = useQuery({
    queryKey: key,
    queryFn: () => apiFetch<TokenRead[]>(`/v1/habits/${habit.id}/shortcut-tokens`),
  });
  const [label, setLabel] = useState(() => t('shortcut.defaultDevice'));
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
    <section className="shortcut-panel" aria-label={t('shortcut.panelLabel', { name: habit.name })}>
      <h3>{t('shortcut.title', { name: habit.name })}</h3>
      <p className="subtle">{t('shortcut.intro')}</p>

      {created ? (
        <div className="card created-token" role="status">
          <p>
            <strong>{t('shortcut.created', { label: created.label })}</strong> {t('shortcut.enterIn')}
          </p>
          <CopyField label={t('shortcut.url')} value={url} />
          <CopyField label={t('shortcut.method')} value="PUT" />
          <CopyField label={t('shortcut.header')} value={`Bearer ${created.token}`} />
          <CopyField label={t('shortcut.jsonField')} value="true" />
          <p className="subtle">{t('shortcut.after')}</p>
          <button type="button" className="button" onClick={() => setCreated(null)}>
            {t('shortcut.hide')}
          </button>
        </div>
      ) : (
        <form className="button-row" onSubmit={submit}>
          <label className="field inline">
            <span>{t('shortcut.device')}</span>
            <input value={label} maxLength={80} required onChange={(e) => setLabel(e.target.value)} />
          </label>
          <button type="submit" className="button primary" disabled={create.isPending}>
            {t('shortcut.create')}
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
                <span className="subtle">
                  {t('shortcut.tokenInfo', {
                    created: format.dateTime(token.created_at),
                    used: format.dateTime(token.last_used_at),
                  })}
                </span>
              </span>
              <button
                type="button"
                className="button"
                onClick={() => revoke.mutate(token.id)}
                aria-label={t('shortcut.revokeLabel', { label: token.label })}
              >
                {t('shortcut.revoke')}
              </button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && <p className="error" role="alert">{errorText(revoke.error)}</p>}
    </section>
  );
}
