import { Navigate } from 'react-router-dom';

export function StartPage() {
  // Laptop: week overview; phone: check off quickly
  const wide = window.matchMedia('(min-width: 60rem)').matches;
  return <Navigate to={wide ? '/woche' : '/heute'} replace />;
}
