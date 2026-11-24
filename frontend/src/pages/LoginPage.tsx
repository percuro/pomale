import { APP_NAME } from '../app/brand';
import { useState, type FormEvent } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, errorText } from '../lib/api';
import type { Me } from '../lib/types';
import { signedIn } from '../hooks/useMe';

export function LoginPage() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const login = useMutation({
    mutationFn: () =>
      apiFetch<Me>('/v1/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
    onSuccess: (me) => signedIn(queryClient, me),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate();
  };

  return (
    <main className="center">
      <form className="card login" onSubmit={submit}>
        <h1>{APP_NAME}</h1>
        <label className="field">
          <span>Benutzername</span>
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
          <span>Passwort</span>
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
          {login.isPending ? 'Anmelden …' : 'Anmelden'}
        </button>
      </form>
    </main>
  );
}
