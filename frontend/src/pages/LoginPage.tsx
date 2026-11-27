import { APP_NAME } from '../app/brand';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import type { Me } from '../lib/types';
import { useMeta } from '../hooks/useMeta';
import { useCallbackParams } from '../hooks/useCallbackParams';
import { signedIn } from '../hooks/useMe';
import { useErrorText, useT } from '../i18n/context';
import { codeMessage } from '../i18n/core';
import { LanguageSwitcher } from '../components/layout/LanguageSwitcher';
import { OidcButton } from '../components/account/OidcButton';

export function LoginPage() {
  const queryClient = useQueryClient();
  const t = useT();
  const errorText = useErrorText();
  const meta = useMeta();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  // An error from the OIDC callback (/login#error=…), read once
  const callbackError = useCallbackParams().error ?? null;
  const login = useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      apiFetch<Me>('/v1/auth/login', { method: 'POST', body: JSON.stringify(credentials) }),
    onSuccess: (me) => signedIn(queryClient, me),
  });
  const demo = meta.data?.demo ?? null;
  const passwordLogin = meta.data?.password_login ?? true;
  const oidc = meta.data?.oidc != null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ username, password });
  };

  return (
    <main className="center">
      <form className="card login" onSubmit={submit}>
        <h1>{APP_NAME}</h1>
        {callbackError && (
          <p className="error" role="alert">
            {codeMessage(callbackError, t) ?? t('error.unknown')}
          </p>
        )}
        {demo && (
          <div className="notice info demo-login">
            <p>{t('demo.loginHint', { username: demo.username, password: demo.password })}</p>
            <button
              type="button"
              className="button primary"
              disabled={login.isPending}
              onClick={() => login.mutate(demo)}
            >
              {t('demo.signIn')}
            </button>
          </div>
        )}
        {passwordLogin && (
          <>
            <label className="field">
              <span>{t('field.username')}</span>
              <input
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('field.password')}</span>
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {login.isError && <p className="error" role="alert">{errorText(login.error)}</p>}
            <button type="submit" className="button primary" disabled={login.isPending}>
              {login.isPending ? t('login.submitting') : t('login.submit')}
            </button>
          </>
        )}
        {oidc && (
          <>
            {passwordLogin && <p className="subtle divider">{t('login.or')}</p>}
            <OidcButton
              action="signIn"
              path="/v1/auth/oidc/start"
              body={() => ({ purpose: 'login' })}
              primary={!passwordLogin}
            />
          </>
        )}
        {meta.data?.registration === 'open' && passwordLogin && (
          <p className="subtle">
            {t('login.noAccount')} <Link to="/register">{t('login.register')}</Link>
          </p>
        )}
        <LanguageSwitcher />
      </form>
    </main>
  );
}
