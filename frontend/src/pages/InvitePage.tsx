import { useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { APP_NAME } from '../app/brand';
import { LanguageSwitcher } from '../components/layout/LanguageSwitcher';
import { NewPasswordFields } from '../components/account/NewPasswordFields';
import { OidcButton } from '../components/account/OidcButton';
import { useMeta } from '../hooks/useMeta';
import { signedIn } from '../hooks/useMe';
import { useErrorText, useI18n } from '../i18n/context';
import { apiFetch } from '../lib/api';
import { browserTimeZone } from '../lib/browser';
import type { InvitationInfo, Me } from '../lib/types';

/**
 * Accept an invitation or a password-reset link: /invite#<token>.
 * The token is in the fragment, so it never reaches the server's logs; it is sent in the body.
 */
export function InvitePage() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const token = useLocation().hash.slice(1);
  const info = useQuery({
    queryKey: ['invitation', token],
    queryFn: () =>
      apiFetch<InvitationInfo>('/v1/invitations/inspect', { method: 'POST', body: JSON.stringify({ token }) }),
    enabled: token.length > 0,
    retry: false,
    staleTime: Infinity,
  });

  let content;
  if (!token) {
    content = <p className="error" role="alert">{t('invite.missingToken')}</p>;
  } else if (info.isPending) {
    content = <p>{t('invite.checking')}</p>;
  } else if (info.isError) {
    content = (
      <>
        <p className="error" role="alert">{errorText(info.error)}</p>
        <Link to="/">{t('invite.toApp', { app: APP_NAME })}</Link>
      </>
    );
  } else {
    content = <AcceptForm token={token} info={info.data} />;
  }

  const form = token && info.isSuccess;
  return (
    <main className="center">
      <div className="card login">
        {/* The form has its own heading; a missing or wrong link gets the app's name, like the login */}
        {!form && <h1>{APP_NAME}</h1>}
        {content}
        <LanguageSwitcher />
      </div>
    </main>
  );
}

function AcceptForm({ token, info }: { token: string; info: InvitationInfo }) {
  const { t, format, locale } = useI18n();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const meta = useMeta();
  const passwordLogin = meta.data?.password_login ?? true;
  const oidc = meta.data?.oidc != null;
  const form = useRef<HTMLFormElement>(null);
  const signup = info.purpose === 'signup';
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const mismatch = confirm.length > 0 && password !== confirm;

  const accept = useMutation({
    mutationFn: () =>
      apiFetch<Me>('/v1/invitations/accept', {
        method: 'POST',
        body: JSON.stringify(
          signup
            ? {
                token,
                username,
                password,
                display_name: displayName.trim() || null,
                timezone: browserTimeZone(),
                locale,
              }
            : { token, password },
        ),
      }),
    onSuccess: async (me) => {
      await signedIn(queryClient, me);
      navigate('/', { replace: true });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (password !== confirm) return;
    accept.mutate();
  };

  // With the provider: only the username (signup) has to be valid; no password
  const oidcBody = () => {
    if (!signup) return { token };
    const field = form.current?.elements.namedItem('username') as HTMLInputElement | null;
    if (field && !field.reportValidity()) return null;
    return { token, username, display_name: displayName.trim() || null, timezone: browserTimeZone(), locale };
  };

  return (
    <form className="login-form" onSubmit={submit} ref={form}>
      <h1>{signup ? t('invite.signupTitle') : t('invite.recoverTitle')}</h1>
      <p className="subtle">
        {signup
          ? t(passwordLogin ? 'invite.signupIntro' : 'invite.signupIntroOidc', { app: APP_NAME })
          : t('invite.recoverIntro', { username: info.username ?? '' })}
      </p>
      {signup ? (
        <>
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
        </>
      ) : (
        <input type="text" name="username" autoComplete="username" value={info.username ?? ''} readOnly hidden />
      )}
      {passwordLogin && (
        <>
          <NewPasswordFields password={password} confirm={confirm} onPassword={setPassword} onConfirm={setConfirm} />
          {accept.isError && <p className="error" role="alert">{errorText(accept.error)}</p>}
          <button type="submit" className="button primary" disabled={accept.isPending || mismatch}>
            {signup ? t('invite.signupSubmit') : t('invite.resetSubmit')}
          </button>
        </>
      )}
      {oidc && (
        <>
          {passwordLogin && <p className="subtle divider">{t('login.or')}</p>}
          <OidcButton
            action={signup ? 'continue' : 'link'}
            path="/v1/invitations/oidc"
            body={oidcBody}
            primary={!passwordLogin}
          />
        </>
      )}
      <p className="subtle">{t('invite.expires', { date: format.dateTime(info.expires_at) })}</p>
    </form>
  );
}
