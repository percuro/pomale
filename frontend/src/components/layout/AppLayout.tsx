import { APP_NAME } from '../../app/brand';
import { lazy, Suspense, useEffect, useRef, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation, useNavigationType } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { Me } from '../../lib/types';
import { ME_KEY, useMe } from '../../hooks/useMe';
import { SessionContext } from '../../hooks/useSession';
import { useToday } from '../../hooks/useToday';
import { useI18n } from '../../i18n/context';
import { useMeta } from '../../hooks/useMeta';
import { SyncBridge } from '../sync/SyncBridge';
import { WorkerBridge } from '../sync/WorkerBridge';
import { SyncStatus } from '../sync/SyncStatus';
import { BrandMark } from '../BrandMark';
import { ChartIcon, CheckCircleIcon, ChecklistIcon, UserIcon, WeekIcon } from '../Icons';
import { TimezoneHint } from './TimezoneHint';
import { Loading } from './Loading';
import { loadChunk } from '../../app/lazy';

// Signed out is rare with long sessions: login and setup load when needed
const LoginPage = lazy(() => loadChunk(() => import('../../pages/LoginPage')).then((m) => ({ default: m.LoginPage })));
const SetupPage = lazy(() => loadChunk(() => import('../../pages/SetupPage')).then((m) => ({ default: m.SetupPage })));

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
    return <Loading />;
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
  const { setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(null), [setAccountLocale]);
  if (meta.isPending) {
    return <Loading />;
  }
  return <Suspense fallback={<Loading />}>{meta.data?.setup_needed ? <SetupPage /> : <LoginPage />}</Suspense>;
}

function SignedIn({ me }: { me: Me }) {
  // Older cached "me" from before 0.9 has no day end: midnight
  const { today, beforeDayEnd } = useToday(me.timezone, me.day_end_hour ?? 0, me.today);
  const { t, setAccountLocale } = useI18n();
  useEffect(() => setAccountLocale(me.locale), [me.locale, setAccountLocale]);
  usePageChange();

  return (
    <SessionContext.Provider value={{ me, today, beforeDayEnd }}>
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
      {/* Screen readers hear the name of the page after a change of page */}
      <p id={ANNOUNCER_ID} className="sr-only" role="status" />
      <main id="content" className="content wide" tabIndex={-1}>
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
 *
 * After a change of page (not on the first load, not after a redirect) the focus moves to the
 * start of the content, as after a page load, and the new heading is announced once it shows.
 */
const ANNOUNCER_ID = 'page-announcer';

function announce(text: string) {
  const region = document.getElementById(ANNOUNCER_ID);
  if (region) region.textContent = text;
}

function usePageChange() {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  const firstPath = useRef(true);
  const announcePending = useRef(false);

  useEffect(() => {
    if (firstPath.current) {
      firstPath.current = false;
      return;
    }
    if (navigationType === 'REPLACE') return;
    const main = document.getElementById('content');
    main?.focus({ preventScroll: true });
    // A page from the main chunk is already there; one that still loads its data gets its heading later
    const heading = main?.querySelector('h1')?.textContent?.trim();
    announcePending.current = !heading;
    announce(heading ?? '');
  }, [pathname, navigationType]);

  useEffect(() => {
    const main = document.getElementById('content');
    if (!main) return;
    const update = () => {
      const heading = main.querySelector('h1')?.textContent?.trim();
      const title = heading ? `${heading} · ${APP_NAME}` : APP_NAME;
      if (document.title !== title) document.title = title;
      if (heading && announcePending.current) {
        announcePending.current = false;
        announce(heading);
      }
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
