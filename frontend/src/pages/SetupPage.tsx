import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../lib/api';
import { browserTimeZone } from '../lib/browser';
import type { Me } from '../lib/types';
import { signedIn } from '../hooks/useMe';
import { useErrorText, useI18n } from '../i18n/context';
import { LanguageSwitcher } from '../components/layout/LanguageSwitcher';
import { NewPasswordFields } from '../components/account/NewPasswordFields';

/** First-run setup: create the first account with the token from the server log. */
export function SetupPage() {
  const queryClient = useQueryClient();
  const { t, locale } = useI18n();
  const errorText = useErrorText();
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const mismatch = confirm.length > 0 && password !== confirm;

  const setup = useMutation({
    mutationFn: () =>
      apiFetch<Me>('/v1/setup', {
        method: 'POST',
        body: JSON.stringify({ token: token.trim(), username, password, timezone: browserTimeZone(), locale }),
      }),
    onSuccess: (me) => signedIn(queryClient, me),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) return;
    setup.mutate();
  };

  return (
    <main className="center">
      <form className="card login" onSubmit={submit}>
        <h1>{t('setup.title')}</h1>
        <p className="subtle">{t('setup.intro', { command: 'docker compose logs app' })}</p>
        <label className="field">
          <span>{t('setup.token')}</span>
          <input
            name="setup-token"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </label>
        <label className="field">
          <span>{t('field.username')}</span>
          <input
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            required
            maxLength={32}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <NewPasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
        {setup.isError && <p className="error" role="alert">{errorText(setup.error)}</p>}
        <button type="submit" className="button primary" disabled={setup.isPending || mismatch}>
          {setup.isPending ? t('setup.submitting') : t('setup.submit')}
        </button>
        <LanguageSwitcher />
      </form>
    </main>
  );
}
