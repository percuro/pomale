import { describe, expect, it } from 'vitest';
import type { QueuedOp } from './offline-store';
import { overlay } from './overlay';
import type { Day, DaysResponse, HabitDays } from './types';

const day = (date: string, fields: Partial<Day> = {}): Day => ({
  date,
  planned: true,
  done: false,
  state: 'open',
  version: 0,
  goal_type: 'days',
  target: null,
  paused: false,
  value: null,
  note: null,
  ...fields,
});

const habitBase = {
  cue: null,
  archived: false,
  goal_type: 'days' as const,
  target: null,
  unit: null,
  color: null,
  group_id: null,
  week: null,
};

/** A whole week Monday 23 to Sunday 29 Nov for one habit */
function fullWeek(habit: Partial<HabitDays>, fields: (date: string, i: number) => Partial<Day>): DaysResponse {
  const dates = Array.from({ length: 7 }, (_, i) => `2026-11-${23 + i}`);
  return {
    today: '2026-11-25',
    timezone: 'UTC',
    start: dates[0],
    end: dates[6],
    groups: [],
    habits: [
      {
        ...habitBase,
        id: 1,
        name: 'Water',
        quota: { done: 0, due: 0 },
        ...habit,
        days: dates.map((date, i) => day(date, fields(date, i))),
      },
    ],
  };
}

function week(): DaysResponse {
  const dates = ['2026-11-23', '2026-11-24', '2026-11-25'];
  return {
    today: '2026-11-24',
    timezone: 'UTC',
    start: dates[0],
    end: dates[2],
    groups: [],
    habits: [
      {
        ...habitBase,
        id: 1,
        name: 'Lesen',
        quota: { done: 0, due: 1 },
        days: [
          day(dates[0]),
          day(dates[1], { planned: false, state: 'not_planned' }),
          day(dates[2], { state: 'future' }),
        ],
      },
    ],
  };
}

const op = (date: string, done: boolean, value?: number): QueuedOp => ({
  value,
  op_id: date,
  habit_id: 1,
  date,
  done,
  base_version: 0,
  created_at: 0,
  user_id: 1,
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

  it('applies a pending amount to a quantity goal', () => {
    const data = fullWeek({ goal_type: 'quantity', target: 8 }, () => ({ goal_type: 'quantity', target: 8, value: 0 }));
    const partial = overlay(data, [op('2026-11-25', true, 3)], '2026-11-25').habits[0];
    expect(partial.days[2]).toMatchObject({ state: 'partial', value: 3, done: false, pending: true });
    expect(partial.quota).toEqual({ done: 0, due: 2 });
    const reached = overlay(data, [op('2026-11-25', true, 8)], '2026-11-25').habits[0];
    expect(reached.days[2]).toMatchObject({ state: 'done', value: 8, done: true });
    expect(reached.quota).toEqual({ done: 1, due: 3 });
    // A change queued as done (no value) sets the target
    expect(overlay(data, [op('2026-11-25', true)], '2026-11-25').habits[0].days[2].value).toBe(8);
  });

  it('recomputes the weekly progress with pending check-ins', () => {
    const data = fullWeek(
      { goal_type: 'weekly_count', target: 2, week: { done: 1, target: 2 } },
      (_, i) => ({ goal_type: 'weekly_count', target: 2, done: i === 0, state: i === 0 ? 'done' : 'not_planned' }),
    );
    const habit = overlay(data, [op('2026-11-25', true)], '2026-11-25').habits[0];
    expect(habit.week).toEqual({ done: 2, target: 2 });
    expect(habit.days[2].state).toBe('done');
    expect(habit.quota).toEqual({ done: 2, due: 2 });
  });

  it('keeps paused days out of the quota', () => {
    const data = fullWeek({}, (_, i) => (i < 2 ? { planned: false, paused: true, state: 'paused' } : {}));
    const habit = overlay(data, [], '2026-11-25').habits[0];
    expect(habit.days.slice(0, 3).map((d) => d.state)).toEqual(['paused', 'paused', 'open']);
    expect(habit.quota).toEqual({ done: 0, due: 0 });
  });
});
