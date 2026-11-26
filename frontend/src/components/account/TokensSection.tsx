import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CopyField } from '../habits/ShortcutPanel';
import { useHabits } from '../../hooks/useHabits';
import { useMeta } from '../../hooks/useMeta';
import { useErrorText, useI18n } from '../../i18n/context';
import { apiFetch } from '../../lib/api';
import {
  activeTokens,
  isExpired,
  TOKEN_EXPIRY_DAYS,
  TOKEN_SCOPES,
  tokenBody,
  tokenFormProblem,
  type TokenExpiry,
  type TokenForm,
} from '../../lib/tokens';
import type { ApiToken, ApiTokenCreated } from '../../lib/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';
const TOKENS_KEY = ['account', 'tokens'] as const;
const API_GUIDE = 'https://github.com/percuro/pomale/blob/main/docs/api.md';

/** Personal API keys for scripts, shortcuts and home automation: read and/or check off, nothing else. */
export function TokensSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const meta = useMeta();
  const habits = useHabits();
  const tokens = useQuery({ queryKey: TOKENS_KEY, queryFn: () => apiFetch<ApiToken[]>('/v1/account/tokens') });
  const empty: TokenForm = { label: '', scopes: ['read'], allHabits: true, habitIds: [], expiresInDays: null };
  const [form, setForm] = useState<TokenForm>(empty);
  const [showProblem, setShowProblem] = useState(false);
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const create = useMutation({
    mutationFn: () =>
      apiFetch<ApiTokenCreated>('/v1/account/tokens', { method: 'POST', body: JSON.stringify(tokenBody(form)) }),
    onSuccess: (token) => {
      setCreated(token);
      setForm(empty);
      setShowProblem(false);
      void queryClient.invalidateQueries({ queryKey: TOKENS_KEY });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/account/tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TOKENS_KEY }),
  });

  const activeHabits = (habits.data ?? []).filter((habit) => !habit.archived_on);
  const names = new Map((habits.data ?? []).map((habit) => [habit.id, habit.name]));
  const active = activeTokens(tokens.data ?? []);
  const problem = tokenFormProblem(form);
  const origin = window.location.origin;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (problem) {
      setShowProblem(true);
      return;
    }
    create.mutate();
  };
  const toggle = <T,>(list: T[], item: T, on: boolean) => (on ? [...list, item] : list.filter((x) => x !== item));

  return (
    <section aria-labelledby="tokens-heading">
      <h2 id="tokens-heading">{t('tokens.title')}</h2>
      <p className="subtle">{t('tokens.intro')}</p>

      {created && (
        <div className="card created-token" role="status">
          <p>
            <strong>{t('tokens.created', { label: created.label })}</strong> {t('tokens.onlyNow')}
          </p>
          <CopyField label={t('tokens.key')} value={created.token} />
          <CopyField
            label={t('tokens.example')}
            value={`curl -H "Authorization: Bearer ${created.token}" ${origin}${API_BASE_URL}/v1/today`}
          />
          <p className="subtle">
            <a href={API_GUIDE} target="_blank" rel="noreferrer">
              {t('tokens.guide')}
            </a>
            {meta.data?.api_docs !== false && (
              <>
                {' · '}
                <a href={`${API_BASE_URL}/openapi.json`} target="_blank" rel="noreferrer">
                  openapi.json
                </a>
              </>
            )}
          </p>
          <div className="button-row">
            <button type="button" className="button" onClick={() => setCreated(null)}>
              {t('tokens.hide')}
            </button>
          </div>
        </div>
      )}

      <form className="card habit-form" onSubmit={submit} noValidate>
        <label className="field">
          <span>{t('tokens.label')}</span>
          <input
            value={form.label}
            maxLength={80}
            placeholder={t('tokens.labelPlaceholder')}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
          />
        </label>
        <fieldset className="weekday-picker">
          <legend>{t('tokens.scopes')}</legend>
          <div className="chips">
            {TOKEN_SCOPES.map((scope) => (
              <label key={scope} className="chip">
                <input
                  type="checkbox"
                  checked={form.scopes.includes(scope)}
                  onChange={(e) => setForm({ ...form, scopes: toggle(form.scopes, scope, e.target.checked) })}
                />
                <span>{t(`tokens.scope.${scope}`)}</span>
              </label>
            ))}
          </div>
          <small className="subtle">{t('tokens.scopesHint')}</small>
        </fieldset>
        <fieldset className="weekday-picker">
          <legend>{t('tokens.habits')}</legend>
          <div className="chips">
            <label className="chip">
              <input type="radio" name="token-habits" checked={form.allHabits} onChange={() => setForm({ ...form, allHabits: true })} />
              <span>{t('tokens.allHabits')}</span>
            </label>
            <label className="chip">
              <input type="radio" name="token-habits" checked={!form.allHabits} onChange={() => setForm({ ...form, allHabits: false })} />
              <span>{t('tokens.someHabits')}</span>
            </label>
          </div>
          {!form.allHabits && (
            <div className="chips">
              {activeHabits.map((habit) => (
                <label key={habit.id} className="chip">
                  <input
                    type="checkbox"
                    checked={form.habitIds.includes(habit.id)}
                    onChange={(e) => setForm({ ...form, habitIds: toggle(form.habitIds, habit.id, e.target.checked) })}
                  />
                  <span>{habit.name}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
        <label className="field">
          <span>{t('tokens.expiry')}</span>
          <select
            value={form.expiresInDays ?? ''}
            onChange={(e) => setForm({ ...form, expiresInDays: (e.target.value ? Number(e.target.value) : null) as TokenExpiry })}
          >
            <option value="">{t('tokens.noExpiry')}</option>
            {TOKEN_EXPIRY_DAYS.map((days) => (
              <option key={days} value={days}>
                {t('tokens.days', { count: days })}
              </option>
            ))}
          </select>
        </label>
        {showProblem && problem && (
          <p className="error" role="alert">
            {t(problem)}
          </p>
        )}
        {create.isError && (
          <p className="error" role="alert">
            {errorText(create.error)}
          </p>
        )}
        <div className="button-row">
          <button type="submit" className="button primary" disabled={create.isPending}>
            {t('tokens.create')}
          </button>
        </div>
      </form>

      {tokens.isSuccess && active.length === 0 && <p className="subtle">{t('tokens.none')}</p>}
      {active.length > 0 && (
        <ul className="token-list card">
          {active.map((token) => (
            <li key={token.id}>
              <span>
                <strong>{token.label}</strong>{' '}
                <span className="subtle">
                  {token.scopes.map((scope) => t(`tokens.scope.${scope}`)).join(', ')}
                  {' · '}
                  {token.habit_ids.length === 0
                    ? t('tokens.allHabits')
                    : token.habit_ids.map((id) => names.get(id) ?? `#${id}`).join(', ')}
                </span>
                <br />
                <span className="subtle">
                  {t('tokens.info', { created: format.dateTime(token.created_at), used: format.dateTime(token.last_used_at) })}
                  {token.expires_at && !isExpired(token) && <> · {t('tokens.expires', { date: format.dateTime(token.expires_at) })}</>}
                </span>
              </span>
              <button
                type="button"
                className="button"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(token.id)}
                aria-label={t('tokens.revokeLabel', { label: token.label })}
              >
                {t('tokens.revoke')}
              </button>
            </li>
          ))}
        </ul>
      )}
      {revoke.isError && (
        <p className="error" role="alert">
          {errorText(revoke.error)}
        </p>
      )}
    </section>
  );
}
