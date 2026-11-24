import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { TodayPage } from '../pages/TodayPage';
import { WeekPage } from '../pages/WeekPage';
import { HabitsPage } from '../pages/HabitsPage';
import { StartPage } from '../pages/StartPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <StartPage /> },
      { path: 'today', element: <TodayPage /> },
      { path: 'week', element: <WeekPage /> },
      { path: 'habits', element: <HabitsPage /> },
      // Paths before 0.4 (bookmarks)
      { path: 'heute', element: <Navigate to="/today" replace /> },
      { path: 'woche', element: <Navigate to="/week" replace /> },
      { path: 'gewohnheiten', element: <Navigate to="/habits" replace /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
