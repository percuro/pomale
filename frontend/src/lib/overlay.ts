import type { QueuedOp } from './offline-store';
import { stateAfter } from './states';
import type { DaysResponse } from './types';

/**
 * Put local, unconfirmed changes on top of the server data and re-evaluate states
 * with the local "today" (stays correct across midnight while offline).
 */
export function overlay(data: DaysResponse, ops: QueuedOp[], today: string): DaysResponse {
  const byKey = new Map(ops.map((op) => [`${op.habit_id}:${op.date}`, op]));
  return {
    ...data,
    today,
    habits: data.habits.map((habit) => {
      const days = habit.days.map((day) => {
        const op = byKey.get(`${habit.id}:${day.date}`);
        const done = op ? op.done : day.done;
        const state = day.date > today ? 'future' : stateAfter(day.planned, done);
        return { ...day, done: state === 'future' ? false : done, state, pending: Boolean(op), conflict: Boolean(op?.conflict) };
      });
      // Same quota rule as the backend (day_service.quota), including local changes
      let done = 0;
      let due = 0;
      for (const day of days) {
        if (!day.planned || day.date > today) continue;
        if (day.date < today || day.done) due += 1;
        if (day.done) done += 1;
      }
      return { ...habit, days, quota: { done, due } };
    }),
  };
}
