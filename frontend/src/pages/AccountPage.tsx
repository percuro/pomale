import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { OnlineOnly } from '../components/common/OnlineOnly';
import { NewPasswordFields } from '../components/account/NewPasswordFields';
import { OidcButton } from '../components/account/OidcButton';
import { RemindersSection } from '../components/account/RemindersSection';
import { LogoutSection } from '../components/account/LogoutSection';
import { useOidcLabel } from '../hooks/useOidcLabel';
import { useMeta } from '../hooks/useMeta';
import { codeMessage } from '../i18n/core';
import { ApiError } from '../lib/api';
import { startOidc, takeHashParams } from '../lib/oidc';
import { forgetLocalSubscription } from '../lib/push';
import { TimezoneSelect } from '../components/account/TimezoneSelect';
import { DayEndSelect } from '../components/account/DayEndSelect';
import { useUpdateAccount } from '../hooks/useAccount';
import { ME_KEY, signedOut } from '../hooks/useMe';
import { useSession } from '../hooks/useSession';
import { useErrorText, useI18n } from '../i18n/context';
import { LOCALES } from '../i18n/core';
import { apiFetch } from '../lib/api';
import type { Locale, SessionInfo } from '../lib/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';
const SESSIONS_KEY = ['account', 'sessions'] as const;

/** The API wants a fresh sign-in at the provider before this change (accounts without a password) */
function needsReauth(error: unknown): boolean {
  return error instanceof ApiError && error.code === 'auth.reauth_required';
}

/** Offered when the API answers auth.reauth_required; comes back to /account#reauth=ok */
function ReauthPrompt() {
  const { t } = useI18n();
  return (
    <div className="reauth">
      <p role="alert">{t('account.reauthNeeded', { provider: useOidcLabel() })}</p>
      <OidcButton
        action="confirm"
        path="/v1/auth/oidc/start"
        body={() => ({ purpose: 'reauth', return_to: '/account' })}
        primary
      />
    </div>
  );
}

export function AccountPage() {
  const { me } = useSession();
  const { t } = useI18n();
  const meta = useMeta();
  // What the OIDC callback reported (#oidc=linked, #reauth=ok, #error=…), read once
  const [flash] = useState(() => takeHashParams());
  const passwordLogin = meta.data?.password_login ?? true;
  return (
    <>
      <div className="page-head">
        <h1>{t('account.title')}</h1>
        <p className="subtle">{t('account.signedInAs', { username: me.username, role: t(`role.${me.role}`) })}</p>
      </div>
      <LogoutSection />
      <OnlineOnly>
        {flash.reauth === 'ok' && <p role="status">{t('account.reauthDone')}</p>}
        <ProfileSection />
        {(meta.data?.oidc != null || me.oidc != null) && <SignInSection flash={flash} />}
        {passwordLogin && <PasswordSection />}
        <RemindersSection />
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
  const [dayEndHour, setDayEndHour] = useState(me.day_end_hour ?? 0);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({
      display_name: displayName.trim() || null,
      timezone: timezone || null,
      locale: locale || null,
      day_end_hour: dayEndHour,
    });
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
        <DayEndSelect value={dayEndHour} onChange={setDayEndHour} />
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
        <div className="button-row">
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
        body: JSON.stringify(
          me.has_password ? { current_password: current, new_password: password } : { new_password: password },
        ),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ME_KEY });
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
      {!me.has_password && <p className="subtle">{t('account.noPasswordIntro')}</p>}
      <form className="card habit-form" onSubmit={submit}>
        {/* Lets password managers know which account this is */}
        <input type="text" name="username" autoComplete="username" value={me.username} readOnly hidden />
        {me.has_password && (
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
        )}
        <NewPasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
        {change.isError &&
          (needsReauth(change.error) ? (
            <ReauthPrompt />
          ) : (
            <p className="error" role="alert">{errorText(change.error)}</p>
          ))}
        {change.isSuccess && <p role="status">{t('account.passwordChanged')}</p>}
        <div className="button-row">
          <button
            type="submit"
            className="button primary"
            disabled={change.isPending || (confirm.length > 0 && password !== confirm)}
          >
            {me.has_password ? t('account.changePassword') : t('account.setPassword')}
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
        <div className="button-row section-actions">
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
      <div className="button-row section-actions">
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
    mutationFn: () =>
      apiFetch<void>('/v1/account', {
        method: 'DELETE',
        body: JSON.stringify(me.has_password ? { password } : {}),
      }),
    onSuccess: async () => {
      await forgetLocalSubscription();
      await signedOut(queryClient);
    },
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
      <div className="button-row section-actions">
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
        error={remove.isError && !needsReauth(remove.error) ? errorText(remove.error) : null}
        onConfirm={() => remove.mutate()}
        onCancel={close}
      >
        <p>{t('account.deleteText', { username: me.username })}</p>
        <p>
          <a href={`${API_BASE_URL}/v1/export.csv`} download>
            {t('account.exportButton')}
          </a>
        </p>
        {me.has_password && (
          <>
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
          </>
        )}
        {needsReauth(remove.error) && <ReauthPrompt />}
      </ConfirmDialog>
    </section>
  );
}

function SignInSection({ flash }: { flash: Record<string, string> }) {
  const { me } = useSession();
  const { t, format } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const meta = useMeta();
  const provider = useOidcLabel();
  const [dialog, setDialog] = useState<'link' | 'unlink' | null>(null);
  const [password, setPassword] = useState('');
  const canUnlink = me.has_password && (meta.data?.password_login ?? true);
  const link = useMutation({
    mutationFn: () =>
      startOidc('/v1/auth/oidc/start', {
        purpose: 'link',
        return_to: '/account',
        ...(me.has_password ? { password } : {}),
      }),
  });
  const unlink = useMutation({
    mutationFn: () => apiFetch<void>('/v1/account/oidc', { method: 'DELETE', body: JSON.stringify({ password }) }),
    onSuccess: () => {
      close();
      void queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
  const close = () => {
    setDialog(null);
    setPassword('');
    link.reset();
    unlink.reset();
  };
  const who = me.oidc ? (me.oidc.email ?? me.oidc.preferred_username ?? me.username) : '';
  const busy = link.isPending || link.isSuccess || unlink.isPending;
  const active = dialog === 'link' ? link : unlink;

  return (
    <section aria-labelledby="signin-heading">
      <h2 id="signin-heading">{t('account.signIn')}</h2>
      {flash.oidc === 'linked' && <p role="status">{t('account.oidcLinkedNow', { provider })}</p>}
      {flash.error && (
        <p className="error" role="alert">
          {codeMessage(flash.error, t) ?? t('error.unknown')}
        </p>
      )}
      <div className="card habit-form">
        {me.oidc ? (
          <p>{t('account.oidcLinked', { provider, who, date: format.dateTime(me.oidc.linked_at) })}</p>
        ) : (
          <p className="subtle">{t('account.oidcNotLinked', { provider })}</p>
        )}
        <div className="button-row">
          {me.oidc
            ? canUnlink && (
                <button type="button" className="button" onClick={() => setDialog('unlink')}>
                  {t('account.oidcUnlink')}
                </button>
              )
            : meta.data?.oidc != null && (
                <button
                  type="button"
                  className="button"
                  onClick={() => (me.has_password ? setDialog('link') : link.mutate())}
                >
                  {t('oidc.link', { provider })}
                </button>
              )}
        </div>
        {!dialog && link.isError && <p className="error" role="alert">{errorText(link.error)}</p>}
      </div>
      <ConfirmDialog
        open={dialog !== null}
        title={dialog === 'link' ? t('account.oidcLinkTitle', { provider }) : t('account.oidcUnlinkTitle', { provider })}
        confirmLabel={dialog === 'link' ? t('oidc.link', { provider }) : t('account.oidcUnlink')}
        danger={dialog === 'unlink'}
        busy={busy}
        error={active.isError ? errorText(active.error) : null}
        onConfirm={() => (dialog === 'link' ? link.mutate() : unlink.mutate())}
        onCancel={close}
      >
        <p>{dialog === 'link' ? t('account.oidcLinkText', { provider }) : t('account.oidcUnlinkText', { provider })}</p>
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
