import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { TodayPage } from '../pages/TodayPage';
import { WeekPage } from '../pages/WeekPage';
import { HabitsPage } from '../pages/HabitsPage';
import { StartPage } from '../pages/StartPage';
import { AccountPage } from '../pages/AccountPage';
import { AdminPage } from '../pages/AdminPage';
import { InvitePage } from '../pages/InvitePage';
import { RegisterPage } from '../pages/RegisterPage';

export const router = createBrowserRouter([
  // Without an account: invitation and password-reset links, self-registration
  { path: '/invite', element: <InvitePage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <StartPage /> },
      { path: 'today', element: <TodayPage /> },
      { path: 'week', element: <WeekPage /> },
      { path: 'habits', element: <HabitsPage /> },
      { path: 'account', element: <AccountPage /> },
      { path: 'admin', element: <AdminPage /> },
      // Paths before 0.4 (bookmarks)
      { path: 'heute', element: <Navigate to="/today" replace /> },
      { path: 'woche', element: <Navigate to="/week" replace /> },
      { path: 'gewohnheiten', element: <Navigate to="/habits" replace /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
