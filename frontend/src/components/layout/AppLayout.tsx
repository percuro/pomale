import { APP_NAME } from '../../app/brand';
import { useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import type { Me } from '../../lib/types';
import { ME_KEY, useMe } from '../../hooks/useMe';
import { SessionContext } from '../../hooks/useSession';
import { useToday } from '../../hooks/useToday';
import { LoginPage } from '../../pages/LoginPage';
import { SetupPage } from '../../pages/SetupPage';
import { useSetupStatus } from '../../hooks/useSetupStatus';
import { clearAll } from '../../lib/offline-store';
import { syncEngine } from '../../lib/sync-engine';
import { SyncBridge } from '../sync/SyncBridge';
import { SyncStatus } from '../sync/SyncStatus';

export function AppLayout() {
  const me = useMe();
  const queryClient = useQueryClient();

  useEffect(() => {
    const onUnauthorized = () => queryClient.setQueryData(ME_KEY, null);
    window.addEventListener('habit:unauthorized', onUnauthorized);
    return () => window.removeEventListener('habit:unauthorized', onUnauthorized);
  }, [queryClient]);

  if (me.isPending) {
    return <main className="center"><p>Lädt …</p></main>;
  }
  if (me.isError) {
    return (
      <main className="center">
        <p role="alert">Server nicht erreichbar.</p>
        <button type="button" className="button" onClick={() => me.refetch()}>Erneut versuchen</button>
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
  if (setup.isPending) {
    return <main className="center"><p>Lädt …</p></main>;
  }
  return setup.data?.needed ? <SetupPage /> : <LoginPage />;
}

function SignedIn({ me }: { me: Me }) {
  const today = useToday(me.timezone, me.today);
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: () => apiFetch<void>('/v1/auth/logout', { method: 'POST' }),
    onSuccess: async () => {
      // Delete local data only after a successful logout
      await clearAll();
      syncEngine.reset();
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
    },
  });

  const onLogout = () => {
    const waiting = syncEngine.getSnapshot().ops.length;
    if (waiting > 0 && !window.confirm(`${waiting} Änderung(en) sind noch nicht übertragen und gehen beim Abmelden verloren. Trotzdem abmelden?`)) {
      return;
    }
    logout.mutate();
  };

  return (
    <SessionContext.Provider value={{ me, today }}>
      <a className="skip-link" href="#inhalt">Zum Inhalt</a>
      <header className="topbar">
        <span className="brand">{APP_NAME}</span>
        <nav className="tabs" aria-label="Ansichten">
          <NavLink to="/heute">Heute</NavLink>
          <NavLink to="/woche">Woche</NavLink>
          <NavLink to="/gewohnheiten">Gewohnheiten</NavLink>
        </nav>
        <button type="button" className="link-button" onClick={onLogout}>
          Abmelden
        </button>
      </header>
      <SyncBridge />
      <main id="inhalt" className="content">
        {logout.isError && <p className="error" role="alert">Abmelden nicht möglich: keine Verbindung.</p>}
        <SyncStatus />
        <Outlet />
      </main>
    </SessionContext.Provider>
  );
}
