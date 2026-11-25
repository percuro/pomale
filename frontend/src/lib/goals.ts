import type { Goal } from '../hooks/useHabits';
import type { GoalType } from './types';

/** Same limits as the backend (models/habit.py) */
export const MAX_TARGET: Record<GoalType, number> = { days: 0, weekly_count: 7, quantity: 9999 };

export function goalValid(goal: Goal): boolean {
  if (goal.goal_type === 'days') return goal.weekdays > 0;
  const target = goal.target ?? 0;
  return target >= 1 && target <= MAX_TARGET[goal.goal_type] && (goal.goal_type === 'weekly_count' || goal.weekdays > 0);
}

export function sameGoal(a: Goal, b: Goal): boolean {
  return a.goal_type === b.goal_type && a.target === b.target && (a.goal_type === 'weekly_count' || a.weekdays === b.weekdays);
}
