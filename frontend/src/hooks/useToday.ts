import { useEffect, useState } from 'react';
import { isBeforeDayEnd, todayIn } from '../lib/dates';

export interface TodayState {
  today: string;
  /** Between midnight and a later day end: "today" is still the calendar day before */
  beforeDayEnd: boolean;
}

/**
 * Today in the configured time zone and day end; updates at the day end (checked every 30 s)
 * and when returning to the app.
 */
export function useToday(timeZone: string, dayEndHour: number, fallback: string): TodayState {
  const compute = (): TodayState => {
    try {
      const now = new Date();
      return { today: todayIn(timeZone, now, dayEndHour), beforeDayEnd: isBeforeDayEnd(timeZone, dayEndHour, now) };
    } catch {
      return { today: fallback, beforeDayEnd: false };
    }
  };
  // Two plain values, so an unchanged tick does not render the app again
  const [today, setToday] = useState(() => compute().today);
  const [beforeDayEnd, setBeforeDayEnd] = useState(() => compute().beforeDayEnd);

  useEffect(() => {
    const update = () => {
      const next = compute();
      setToday(next.today);
      setBeforeDayEnd(next.beforeDayEnd);
    };
    update();
    const timer = window.setInterval(update, 30_000);
    document.addEventListener('visibilitychange', update);
    window.addEventListener('focus', update);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', update);
      window.removeEventListener('focus', update);
    };
    // compute only depends on timeZone/dayEndHour/fallback
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeZone, dayEndHour, fallback]);

  return { today, beforeDayEnd };
}
