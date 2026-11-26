import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { Loading, PageFailed } from '../components/layout/Loading';
import { TodayPage } from '../pages/TodayPage';
import { WeekPage } from '../pages/WeekPage';
import { StartPage } from '../pages/StartPage';
import { lazyPage } from './lazy';

// Today and week are what an app start shows, so they are in the main chunk. Every other page is
// its own chunk, loaded on first use; the service worker precaches all of them for offline use.
export const router = createBrowserRouter([
  // Without an account: invitation and password-reset links, self-registration
  {
    path: '/invite',
    lazy: lazyPage(() => import('../pages/InvitePage'), (m) => m.InvitePage),
    HydrateFallback: Loading,
    errorElement: <PageFailed />,
  },
  {
    path: '/register',
    lazy: lazyPage(() => import('../pages/RegisterPage'), (m) => m.RegisterPage),
    HydrateFallback: Loading,
    errorElement: <PageFailed />,
  },
  {
    path: '/',
    element: <AppLayout />,
    HydrateFallback: Loading,
    children: [
      {
        errorElement: <PageFailed />,
        children: [
          { index: true, element: <StartPage /> },
          { path: 'today', element: <TodayPage /> },
          { path: 'week', element: <WeekPage /> },
          { path: 'habits', lazy: lazyPage(() => import('../pages/HabitsPage'), (m) => m.HabitsPage) },
          { path: 'history', lazy: lazyPage(() => import('../pages/HistoryPage'), (m) => m.HistoryPage) },
          { path: 'account', lazy: lazyPage(() => import('../pages/AccountPage'), (m) => m.AccountPage) },
          { path: 'admin', lazy: lazyPage(() => import('../pages/AdminPage'), (m) => m.AdminPage) },
          // Paths before 0.4 (bookmarks)
          { path: 'heute', element: <Navigate to="/today" replace /> },
          { path: 'woche', element: <Navigate to="/week" replace /> },
          { path: 'gewohnheiten', element: <Navigate to="/habits" replace /> },
          { path: '*', element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
]);
