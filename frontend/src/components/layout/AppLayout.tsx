import { APP_NAME } from '../../app/brand';
import { useEffect, type ReactNode } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { Me } from '../../lib/types';
import { ME_KEY, useMe } from '../../hooks/useMe';
import { SessionContext } from '../../hooks/useSession';
import { useToday } from '../../hooks/useToday';
import { useI18n } from '../../i18n/context';
import { LoginPage } from '../../pages/LoginPage';
import { SetupPage } from '../../pages/SetupPage';
import { useMeta } from '../../hooks/useMeta';
import { SyncBridge } from '../sync/SyncBridge';
import { WorkerBridge } from '../sync/WorkerBridge';
import { SyncStatus } from '../sync/SyncStatus';
import { BrandMark } from '../BrandMark';
import { ChartIcon, CheckCircleIcon, ChecklistIcon, UserIcon, WeekIcon } from '../Icons';
import { TimezoneHint } from './TimezoneHint';

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
  const meta = useMeta();
  const { t, setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(null), [setAccountLocale]);
  if (meta.isPending) {
    return <main className="center"><p>{t('app.loading')}</p></main>;
  }
  return meta.data?.setup_needed ? <SetupPage /> : <LoginPage />;
}

function SignedIn({ me }: { me: Me }) {
  const today = useToday(me.timezone, me.today);
  const { t, setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(me.locale), [me.locale, setAccountLocale]);
  useDocumentTitle();

  return (
    <SessionContext.Provider value={{ me, today }}>
      <a className="skip-link" href="#content">{t('app.skipToContent')}</a>
      <header className="topbar">
        <NavLink to="/" className="brand"><BrandMark />{APP_NAME}</NavLink>
        <nav className="appnav" aria-label={t('nav.label')}>
          <NavItem to="/today" icon={<CheckCircleIcon />}>{t('nav.today')}</NavItem>
          <NavItem to="/week" icon={<WeekIcon />}>{t('nav.week')}</NavItem>
          <NavItem to="/history" icon={<ChartIcon />}>{t('nav.history')}</NavItem>
          <NavItem to="/habits" icon={<ChecklistIcon />}>{t('nav.habits')}</NavItem>
        </nav>
        <span className="spacer" />
        {/* Account, administration and logging out live on the account page: the bar is for places, not actions */}
        <NavLink to="/account" className="icon-button" aria-label={t('nav.account')}>
          <UserIcon />
        </NavLink>
      </header>
      <SyncBridge owner={me} />
      <WorkerBridge />
      <main id="content" className="content wide">
        <TimezoneHint me={me} />
        <SyncStatus />
        <Outlet />
      </main>
    </SessionContext.Provider>
  );
}

/** One place of the navigation: icon and a short word; the active one gets the highlight. */
function NavItem({ to, icon, children }: { to: string; icon: ReactNode; children: ReactNode }) {
  return (
    <NavLink to={to}>
      <span className="nav-icon">{icon}</span>
      <span className="nav-label">{children}</span>
    </NavLink>
  );
}

/**
 * The window title follows the heading of the page ("Week · pomale"): an installed
 * app shows it in its window and in the task switcher, a browser in its tab.
 */
function useDocumentTitle() {
  useEffect(() => {
    const main = document.getElementById('content');
    if (!main) return;
    const update = () => {
      const heading = main.querySelector('h1')?.textContent?.trim();
      const title = heading ? `${heading} · ${APP_NAME}` : APP_NAME;
      if (document.title !== title) document.title = title;
    };
    update();
    const observer = new MutationObserver(update);
    observer.observe(main, { childList: true, subtree: true, characterData: true });
    return () => {
      observer.disconnect();
      document.title = APP_NAME;
    };
  }, []);
}
