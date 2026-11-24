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
      { path: 'heute', element: <TodayPage /> },
      { path: 'woche', element: <WeekPage /> },
      { path: 'gewohnheiten', element: <HabitsPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);
