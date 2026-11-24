import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { syncEngine } from '../../lib/sync-engine';
import type { CheckinResponse, DaysResponse } from '../../lib/types';
import { DAYS_KEY } from '../../hooks/useDays';

function applyResponse(data: DaysResponse | undefined, response: CheckinResponse): DaysResponse | undefined {
  if (!data) return data;
  return {
    ...data,
    habits: data.habits.map((habit) =>
      habit.id !== response.habit_id
        ? habit
        : {
            ...habit,
            days: habit.days.map((day) =>
              day.date !== response.date
                ? day
                : { ...day, done: response.done, state: response.state, version: response.version },
            ),
          },
    ),
  };
}

/** Connects the change queue with the query cache and triggers sending. */
export function SyncBridge() {
  const queryClient = useQueryClient();

  useEffect(() => {
    let refresh: number | undefined;
    syncEngine.onApplied = (response) => {
      queryClient.setQueriesData<DaysResponse>({ queryKey: DAYS_KEY }, (data) => applyResponse(data, response));
      window.clearTimeout(refresh);
      refresh = window.setTimeout(() => queryClient.invalidateQueries({ queryKey: DAYS_KEY }), 1500);
    };
    const kick = () => {
      if (document.visibilityState === 'visible') void syncEngine.flush();
    };
    void syncEngine.flush();
    window.addEventListener('online', kick);
    document.addEventListener('visibilitychange', kick);
    const timer = window.setInterval(() => {
      if (syncEngine.getSnapshot().ops.some((op) => !op.conflict)) kick();
    }, 30_000);
    return () => {
      syncEngine.onApplied = () => {};
      window.clearTimeout(refresh);
      window.clearInterval(timer);
      window.removeEventListener('online', kick);
      document.removeEventListener('visibilitychange', kick);
    };
  }, [queryClient]);

  return null;
}
