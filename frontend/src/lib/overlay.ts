import { evaluate, type RawDay } from './evaluate';
import type { QueuedOp } from './offline-store';
import type { Day, DaysResponse, HabitDays } from './types';

/** The raw day after a local change: `value` for quantity goals, else `done`. */
function rawDay(day: Day, op: QueuedOp | undefined): RawDay {
  let done = day.done;
  let value = day.value ?? 0;
  if (op) {
    done = op.done;
    if (day.goal_type === 'quantity') value = op.value ?? (op.done ? (day.target ?? 1) : 0);
  }
  return { date: day.date, goal_type: day.goal_type, target: day.target, planned: day.planned, paused: day.paused, done, value };
}

/**
 * Put local, unconfirmed changes on top of the server data and re-evaluate states with
 * the local "today" (stays correct across midnight while offline). Same rules as the
 * backend (lib/evaluate.ts). The loaded ranges are whole weeks.
 */
export function overlay(data: DaysResponse, ops: QueuedOp[], today: string): DaysResponse {
  const byKey = new Map(ops.map((op) => [`${op.habit_id}:${op.date}`, op]));
  return {
    ...data,
    today,
    habits: data.habits.map((habit): HabitDays => {
      const raw = habit.days.map((day) => rawDay(day, byKey.get(`${habit.id}:${day.date}`)));
      const result = evaluate(raw, today, data.start, data.end);
      const days = habit.days.map((day, i) => {
        const op = byKey.get(`${habit.id}:${day.date}`);
        const evaluated = result.days[i];
        return {
          ...day,
          state: evaluated.state,
          done: evaluated.done,
          value: day.goal_type === 'quantity' ? raw[i].value : day.value,
          pending: Boolean(op),
          conflict: Boolean(op?.conflict),
        };
      });
      return { ...habit, days, quota: result.quota, week: result.week ?? habit.week };
    }),
  };
}
