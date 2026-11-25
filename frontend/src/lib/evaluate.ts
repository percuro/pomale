/**
 * The same evaluation as the backend (backend/app/services/day_service.py, `evaluate`):
 * states, quota and weekly progress from raw days. The web app runs it on top of
 * unconfirmed offline changes. Both are checked against
 * backend/tests/fixtures/quota_cases.json (see evaluate.test.ts).
 */
import { addDays, weekStart } from './dates';
import type { DayState, GoalType, Quota } from './types';

export interface RawDay {
  date: string;
  goal_type: GoalType;
  /** quantity: per day; weekly_count: this week's target; days: null */
  target: number | null;
  /** due (days, quantity) or counting toward the week (weekly_count); false on paused days */
  planned: boolean;
  paused: boolean;
  /** checked off (days, weekly_count) */
  done: boolean;
  /** quantity: amount so far */
  value: number;
}

export interface EvaluatedDay {
  date: string;
  state: DayState;
  /** days and weekly goals: checked off; quantity goals: target reached */
  done: boolean;
}

export interface Evaluation {
  days: EvaluatedDay[];
  quota: Quota;
  /** the week that contains today, for weekly goals only */
  week: { done: number; target: number } | null;
}

function stateOf(day: RawDay, today: string, counted: number, weekChecked: number): [DayState, boolean, boolean] {
  if (day.date > today) return ['future', false, false];
  if (day.goal_type === 'weekly_count') {
    const target = day.target ?? 0;
    if (day.done) {
      if (day.planned && counted < target) return ['done', true, true];
      return ['extra_done', true, false];
    }
    if (day.paused) return ['paused', false, false];
    if (day.planned && day.date === today && weekChecked < target) return ['open', false, false];
    // past days without a check-in are never "missed" for weekly goals
    return ['not_planned', false, false];
  }
  if (day.goal_type === 'quantity') {
    const reached = day.target !== null && day.value >= day.target;
    if (day.planned) {
      if (reached) return ['done', true, false];
      return [day.value > 0 ? 'partial' : 'open', false, false];
    }
    if (day.value > 0) return ['extra_done', reached, false];
    return [day.paused ? 'paused' : 'not_planned', false, false];
  }
  if (day.done) return [day.planned ? 'done' : 'extra_done', true, false];
  if (day.planned) return ['open', false, false];
  return [day.paused ? 'paused' : 'not_planned', false, false];
}

/** `days` should cover whole weeks (Monday to Sunday) for weekly goals to be exact. */
export function evaluate(days: RawDay[], today: string, start: string, end: string): Evaluation {
  const result: EvaluatedDay[] = [];
  let totalDone = 0;
  let totalDue = 0;
  let week: Evaluation['week'] = null;

  const byWeek = new Map<string, RawDay[]>();
  for (const day of [...days].sort((a, b) => a.date.localeCompare(b.date))) {
    const monday = weekStart(day.date);
    byWeek.set(monday, [...(byWeek.get(monday) ?? []), day]);
  }

  for (const [monday, weekDays] of byWeek) {
    const sunday = addDays(monday, 6);
    const inRange = monday <= end && sunday >= start;
    const weekly = weekDays.filter((d) => d.goal_type === 'weekly_count');
    const weekTarget = weekly.length ? (weekly[0].target ?? 0) : 0;
    const weekChecked = weekly.filter((d) => d.planned && d.done && d.date <= today).length;
    let counted = 0;
    let weekDone = 0;
    let weekDue = 0;
    for (const day of weekDays) {
      const [state, done, counts] = stateOf(day, today, counted, weekChecked);
      if (counts) counted += 1;
      if (day.date >= start && day.date <= end) {
        result.push({ date: day.date, state, done });
        if (day.goal_type !== 'weekly_count' && day.planned && day.date <= today) {
          if (day.date < today || done) weekDue += 1;
          if (done) weekDone += 1;
        }
      }
    }
    if (weekly.length) {
      if (sunday < today) {
        weekDue += weekTarget;
        weekDone += Math.min(counted, weekTarget);
      } else if (monday <= today) {
        weekDue += counted;
        weekDone += counted;
      }
      if (monday <= today && today <= sunday) week = { done: counted, target: weekTarget };
    }
    if (inRange) {
      totalDone += weekDone;
      totalDue += weekDue;
    }
  }
  return { days: result, quota: { done: totalDone, due: totalDue }, week };
}
