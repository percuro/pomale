import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, errorText } from '../lib/api';
import type { Me } from '../lib/types';
import { signedIn } from '../hooks/useMe';

/** First-run setup: create the first account with the token from the server log. */
export function SetupPage() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const mismatch = confirm.length > 0 && password !== confirm;

  const setup = useMutation({
    mutationFn: () =>
      apiFetch<Me>('/v1/setup', {
        method: 'POST',
        body: JSON.stringify({ token: token.trim(), username, password }),
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
        <h1>Einrichtung</h1>
        <p className="subtle">
          Noch gibt es keinen Zugang. Das Setup-Token steht im Protokoll des Servers
          (<code>docker compose logs app</code>).
        </p>
        <label className="field">
          <span>Setup-Token</span>
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
          <span>Benutzername</span>
          <input
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            required
            maxLength={80}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Passwort (mindestens 12 Zeichen)</span>
          <input
            name="new-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <label className="field">
          <span>Passwort wiederholen</span>
          <input
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            aria-invalid={mismatch}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </label>
        {mismatch && <p className="error" role="alert">Die Passwörter stimmen nicht überein.</p>}
        {setup.isError && <p className="error" role="alert">{errorText(setup.error)}</p>}
        <button type="submit" className="button primary" disabled={setup.isPending || mismatch}>
          {setup.isPending ? 'Wird angelegt …' : 'Zugang anlegen'}
        </button>
      </form>
    </main>
  );
}
