import { APP_NAME } from '../../app/brand';
import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import type { Me } from '../../lib/types';
import { ME_KEY, signedOut, useMe } from '../../hooks/useMe';
import { SessionContext } from '../../hooks/useSession';
import { useToday } from '../../hooks/useToday';
import { useI18n } from '../../i18n/context';
import { LoginPage } from '../../pages/LoginPage';
import { SetupPage } from '../../pages/SetupPage';
import { useSetupStatus } from '../../hooks/useSetupStatus';
import { syncEngine } from '../../lib/sync-engine';
import { SyncBridge } from '../sync/SyncBridge';
import { SyncStatus } from '../sync/SyncStatus';

export function AppLayout() {
  const me = useMe();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  useEffect(() => {
    const onUnauthorized = () => queryClient.setQueryData(ME_KEY, null);
    window.addEventListener('habit:unauthorized', onUnauthorized);
    return () => window.removeEventListener('habit:unauthorized', onUnauthorized);
  }, [queryClient]);

  if (me.isPending) {
    return <main className="center"><p>{t('app.loading')}</p></main>;
  }
  if (me.isError) {
    return (
      <main className="center">
        <p role="alert">{t('app.serverUnreachable')}</p>
        <button type="button" className="button" onClick={() => me.refetch()}>{t('app.retry')}</button>
      </main>
    );
  }
  if (!me.data) {
    return <SignedOut />;
  }
  return <SignedIn me={me.data} />;
}

function SignedOut() {
  const setup = useSetupStatus();
  const { t, setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(null), [setAccountLocale]);
  if (setup.isPending) {
    return <main className="center"><p>{t('app.loading')}</p></main>;
  }
  return setup.data?.needed ? <SetupPage /> : <LoginPage />;
}

function SignedIn({ me }: { me: Me }) {
  const today = useToday(me.timezone, me.today);
  const queryClient = useQueryClient();
  const { t, setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(me.locale), [me.locale, setAccountLocale]);

  const logout = useMutation({
    mutationFn: () => apiFetch<void>('/v1/auth/logout', { method: 'POST' }),
    // Forget local data only after a successful logout
    onSuccess: () => signedOut(queryClient),
  });

  const onLogout = () => {
    const waiting = syncEngine.getSnapshot().ops.length;
    if (waiting > 0 && !window.confirm(t('logout.pending', { count: waiting }))) {
      return;
    }
    logout.mutate();
  };

  return (
    <SessionContext.Provider value={{ me, today }}>
      <a className="skip-link" href="#content">{t('app.skipToContent')}</a>
      <header className="topbar">
        <span className="brand">{APP_NAME}</span>
        <nav className="tabs" aria-label={t('nav.label')}>
          <NavLink to="/today">{t('nav.today')}</NavLink>
          <NavLink to="/week">{t('nav.week')}</NavLink>
          <NavLink to="/habits">{t('nav.habits')}</NavLink>
        </nav>
        <button type="button" className="link-button" onClick={onLogout}>
          {t('nav.logout')}
        </button>
      </header>
      <SyncBridge owner={me} />
      <main id="content" className="content">
        {logout.isError && <p className="error" role="alert">{t('logout.failed')}</p>}
        <SyncStatus />
        <Outlet />
      </main>
    </SessionContext.Provider>
  );
}
