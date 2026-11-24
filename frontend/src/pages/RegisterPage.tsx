import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { LanguageSwitcher } from '../components/layout/LanguageSwitcher';
import { NewPasswordFields } from '../components/account/NewPasswordFields';
import { useMeta } from '../hooks/useMeta';
import { signedIn } from '../hooks/useMe';
import { useErrorText, useI18n } from '../i18n/context';
import { apiFetch } from '../lib/api';
import { browserTimeZone } from '../lib/browser';
import type { Me } from '../lib/types';

/** Self-registration; only offered when the instance runs with REGISTRATION=open. */
export function RegisterPage() {
  const { t, locale } = useI18n();
  const errorText = useErrorText();
  const meta = useMeta();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const mismatch = confirm.length > 0 && password !== confirm;

  const register = useMutation({
    mutationFn: () =>
      apiFetch<Me>('/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          username,
          password,
          display_name: displayName.trim() || null,
          timezone: browserTimeZone(),
          locale,
        }),
      }),
    onSuccess: async (me) => {
      await signedIn(queryClient, me);
      navigate('/', { replace: true });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) return;
    register.mutate();
  };

  const closed = meta.data && meta.data.registration !== 'open';

  return (
    <main className="center">
      <div className="card login">
        <h1>{t('register.title')}</h1>
        {meta.isPending && <p>{t('app.loading')}</p>}
        {closed && <p className="error" role="alert">{t('error.registration.closed')}</p>}
        {meta.data?.registration === 'open' && (
          <form className="login-form" onSubmit={submit}>
            <label className="field">
              <span>{t('field.username')}</span>
              <input
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
                required
                minLength={3}
                maxLength={32}
                pattern="[A-Za-z0-9._\-]{3,32}"
                aria-describedby="username-hint"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
              <small id="username-hint" className="subtle">{t('field.usernameHint')}</small>
            </label>
            <label className="field">
              <span>{t('field.displayName')}</span>
              <input name="name" autoComplete="nickname" maxLength={80} value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </label>
            <NewPasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
            {register.isError && <p className="error" role="alert">{errorText(register.error)}</p>}
            <button type="submit" className="button primary" disabled={register.isPending || mismatch}>
              {register.isPending ? t('register.submitting') : t('register.submit')}
            </button>
          </form>
        )}
        <p className="subtle">
          {t('register.haveAccount')} <Link to="/">{t('register.toLogin')}</Link>
        </p>
        <LanguageSwitcher />
      </div>
    </main>
  );
}
