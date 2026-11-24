import { describe, expect, it } from 'vitest';
import type { QueuedOp } from './offline-store';
import { overlay } from './overlay';
import type { DaysResponse } from './types';

function week(): DaysResponse {
  const dates = ['2026-11-23', '2026-11-24', '2026-11-25'];
  return {
    today: '2026-11-24',
    timezone: 'UTC',
    start: dates[0],
    end: dates[2],
    habits: [
      {
        id: 1,
        name: 'Lesen',
        cue: null,
        archived: false,
        quota: { done: 0, due: 1 },
        days: [
          { date: dates[0], planned: true, done: false, state: 'open', version: 0 },
          { date: dates[1], planned: false, done: false, state: 'not_planned', version: 0 },
          { date: dates[2], planned: true, done: false, state: 'future', version: 0 },
        ],
      },
    ],
  };
}

const op = (date: string, done: boolean): QueuedOp => ({
  op_id: date,
  habit_id: 1,
  date,
  done,
  base_version: 0,
  created_at: 0,
});

describe('overlay', () => {
  it('applies pending changes and recomputes the quota', () => {
    const habit = overlay(week(), [op('2026-11-23', true)], '2026-11-24').habits[0];
    expect(habit.days[0]).toMatchObject({ done: true, state: 'done', pending: true });
    expect(habit.quota).toEqual({ done: 1, due: 1 });
  });

  it('marks unplanned done days as extra and keeps them out of the quota', () => {
    const habit = overlay(week(), [op('2026-11-24', true)], '2026-11-24').habits[0];
    expect(habit.days[1].state).toBe('extra_done');
    expect(habit.quota).toEqual({ done: 0, due: 1 });
  });

  it('re-evaluates future days with the local today (offline across midnight)', () => {
    const habit = overlay(week(), [], '2026-11-25').habits[0];
    expect(habit.days[2].state).toBe('open');
    expect(habit.quota).toEqual({ done: 0, due: 1 });
  });

  it('never shows a future day as done', () => {
    const habit = overlay(week(), [op('2026-11-25', true)], '2026-11-24').habits[0];
    expect(habit.days[2]).toMatchObject({ state: 'future', done: false });
  });
});
