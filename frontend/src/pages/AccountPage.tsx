import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { OnlineOnly } from '../components/common/OnlineOnly';
import { NewPasswordFields } from '../components/account/NewPasswordFields';
import { TimezoneSelect } from '../components/account/TimezoneSelect';
import { useUpdateAccount } from '../hooks/useAccount';
import { signedOut } from '../hooks/useMe';
import { useSession } from '../hooks/useSession';
import { useErrorText, useI18n } from '../i18n/context';
import { LOCALES } from '../i18n/core';
import { apiFetch } from '../lib/api';
import type { Locale, SessionInfo } from '../lib/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';
const SESSIONS_KEY = ['account', 'sessions'] as const;

export function AccountPage() {
  const { me } = useSession();
  const { t } = useI18n();
  return (
    <>
      <div className="page-head">
        <h1>{t('account.title')}</h1>
        <p className="subtle">{t('account.signedInAs', { username: me.username, role: t(`role.${me.role}`) })}</p>
      </div>
      <OnlineOnly>
        <ProfileSection />
        <PasswordSection />
        <SessionsSection />
        <ExportSection />
        <DeleteSection />
      </OnlineOnly>
    </>
  );
}

function ProfileSection() {
  const { me } = useSession();
  const { t } = useI18n();
  const errorText = useErrorText();
  const update = useUpdateAccount();
  const [displayName, setDisplayName] = useState(me.display_name ?? '');
  const [timezone, setTimezone] = useState(me.timezone_setting ?? '');
  const [locale, setLocale] = useState<Locale | ''>(me.locale ?? '');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ display_name: displayName.trim() || null, timezone: timezone || null, locale: locale || null });
  };

  return (
    <section aria-labelledby="profile-heading">
      <h2 id="profile-heading">{t('account.profile')}</h2>
      <form className="card habit-form" onSubmit={submit}>
        <label className="field">
          <span>{t('field.displayName')}</span>
          <input maxLength={80} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
        </label>
        <TimezoneSelect value={timezone} serverDefault={me.default_timezone} onChange={setTimezone} />
        <label className="field">
          <span>{t('account.language')}</span>
          <select value={locale} onChange={(e) => setLocale(e.target.value as Locale | '')}>
            <option value="">{t('account.languageBrowser')}</option>
            {LOCALES.map((option) => (
              <option key={option} value={option} lang={option}>
                {t(`language.${option}`)}
              </option>
            ))}
          </select>
        </label>
        {update.isError && <p className="error" role="alert">{errorText(update.error)}</p>}
        {update.isSuccess && <p role="status">{t('common.saved')}</p>}
        <div className="actions">
          <button type="submit" className="button primary" disabled={update.isPending}>
            {t('common.save')}
          </button>
        </div>
      </form>
    </section>
  );
}

function PasswordSection() {
  const { me } = useSession();
  const { t } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const change = useMutation({
    mutationFn: () =>
      apiFetch<void>('/v1/account/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: password }),
      }),
    onSuccess: () => {
      setCurrent('');
      setPassword('');
      setConfirm('');
      void queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) return;
    change.mutate();
  };

  return (
    <section aria-labelledby="password-heading">
      <h2 id="password-heading">{t('account.password')}</h2>
      <form className="card habit-form" onSubmit={submit}>
        {/* Lets password managers know which account this is */}
        <input type="text" name="username" autoComplete="username" value={me.username} readOnly hidden />
        <label className="field">
          <span>{t('account.currentPassword')}</span>
          <input
            type="password"
            name="current-password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>
        <NewPasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
        {change.isError && <p className="error" role="alert">{errorText(change.error)}</p>}
        {change.isSuccess && <p role="status">{t('account.passwordChanged')}</p>}
        <div className="actions">
          <button
            type="submit"
            className="button primary"
            disabled={change.isPending || (confirm.length > 0 && password !== confirm)}
          >
            {t('account.changePassword')}
          </button>
        </div>
      </form>
    </section>
  );
}

function SessionsSection() {
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: SESSIONS_KEY,
    queryFn: () => apiFetch<SessionInfo[]>('/v1/account/sessions'),
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: SESSIONS_KEY });
  const revoke = useMutation({
    mutationFn: (id: number) => apiFetch<void>(`/v1/account/sessions/${id}`, { method: 'DELETE' }),
    onSuccess: refresh,
  });
  const revokeOthers = useMutation({
    mutationFn: () => apiFetch<void>('/v1/account/sessions/revoke-others', { method: 'POST' }),
    onSuccess: refresh,
  });
  const others = (sessions.data ?? []).filter((session) => !session.current);

  return (
    <section aria-labelledby="sessions-heading">
      <h2 id="sessions-heading">{t('account.sessions')}</h2>
      <p className="subtle">{t('account.sessionsIntro')}</p>
      {sessions.isPending && <p>{t('app.loading')}</p>}
      {sessions.isError && <p className="error" role="alert">{errorText(sessions.error)}</p>}
      <ul className="token-list card">
        {(sessions.data ?? []).map((session) => {
          const device = session.device ?? t('account.unknownDevice');
          return (
            <li key={session.id}>
              <span>
                <strong>{device}</strong>
                {session.current && <> ({t('account.thisDevice')})</>}
                <span className="subtle">
                  {' · '}
                  {t('account.sessionInfo', {
                    created: format.dateTime(session.created_at),
                    seen: format.dateTime(session.last_seen_at),
                  })}
                </span>
              </span>
              {!session.current && (
                <button
                  type="button"
                  className="button"
                  disabled={revoke.isPending}
                  onClick={() => revoke.mutate(session.id)}
                  aria-label={t('account.logoutSessionLabel', { device })}
                >
                  {t('account.logoutSession')}
                </button>
              )}
            </li>
          );
        })}
      </ul>
      {(revoke.isError || revokeOthers.isError) && (
        <p className="error" role="alert">{errorText(revoke.error ?? revokeOthers.error)}</p>
      )}
      {others.length > 1 && (
        <div className="actions section-actions">
          <button type="button" className="button" disabled={revokeOthers.isPending} onClick={() => revokeOthers.mutate()}>
            {t('account.logoutOthers')}
          </button>
        </div>
      )}
    </section>
  );
}

function ExportSection() {
  const { t } = useI18n();
  return (
    <section aria-labelledby="export-heading">
      <h2 id="export-heading">{t('account.export')}</h2>
      <p className="subtle">{t('account.exportIntro')}</p>
      <div className="actions section-actions">
        <a className="button" href={`${API_BASE_URL}/v1/export.csv`} download>
          {t('account.exportButton')}
        </a>
      </div>
    </section>
  );
}

function DeleteSection() {
  const { me } = useSession();
  const { t } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const remove = useMutation({
    mutationFn: () => apiFetch<void>('/v1/account', { method: 'DELETE', body: JSON.stringify({ password }) }),
    onSuccess: () => signedOut(queryClient),
  });

  const close = () => {
    setOpen(false);
    setPassword('');
    remove.reset();
  };

  return (
    <section aria-labelledby="delete-heading">
      <h2 id="delete-heading">{t('account.delete')}</h2>
      <p className="subtle">{t('account.deleteIntro')}</p>
      <div className="actions section-actions">
        <button type="button" className="button danger" onClick={() => setOpen(true)}>
          {t('account.deleteButton')}
        </button>
      </div>
      <ConfirmDialog
        open={open}
        title={t('account.deleteTitle')}
        confirmLabel={t('account.deleteConfirm')}
        danger
        busy={remove.isPending}
        error={remove.isError ? errorText(remove.error) : null}
        onConfirm={() => remove.mutate()}
        onCancel={close}
      >
        <p>{t('account.deleteText', { username: me.username })}</p>
        <p>
          <a href={`${API_BASE_URL}/v1/export.csv`} download>
            {t('account.exportButton')}
          </a>
        </p>
        <input type="text" name="username" autoComplete="username" value={me.username} readOnly hidden />
        <label className="field">
          <span>{t('account.deletePassword')}</span>
          <input
            type="password"
            name="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
      </ConfirmDialog>
    </section>
  );
}
