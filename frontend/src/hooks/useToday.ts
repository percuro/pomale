import { useEffect, useState } from 'react';
import { todayIn } from '../lib/dates';

/** Today in the configured time zone; updates at midnight and when returning to the app. */
export function useToday(timeZone: string, fallback: string): string {
  const compute = () => {
    try {
      return todayIn(timeZone);
    } catch {
      return fallback;
    }
  };
  const [today, setToday] = useState(compute);

  useEffect(() => {
    const update = () => setToday(compute());
    const timer = window.setInterval(update, 30_000);
    document.addEventListener('visibilitychange', update);
    window.addEventListener('focus', update);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', update);
      window.removeEventListener('focus', update);
    };
    // compute only depends on timeZone/fallback
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeZone, fallback]);

  return today;
}
