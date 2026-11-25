import { describe, expect, it } from 'vitest';
import { addDays } from './dates';
import { evaluate, type RawDay } from './evaluate';
import type { GoalType } from './types';

interface CaseWeek {
  start: string;
  goal_type: GoalType | GoalType[];
  target: number | null | (number | null)[];
  planned: string;
  paused: string;
  done: string;
  value?: number[] | null;
}

interface Case {
  name: string;
  today: string;
  start: string;
  end: string;
  weeks: CaseWeek[];
  expect: {
    states: string[];
    quota: { done: number; due: number };
    week: { done: number; target: number } | null;
  };
}

// The backend runs the same file (backend/tests/test_quota_cases.py)
const files = import.meta.glob<{ cases: Case[] }>('../../../backend/tests/fixtures/quota_cases.json', {
  eager: true,
  import: 'default',
});
const cases = Object.values(files).flatMap((file) => file.cases);

function perDay<T>(value: T | T[], index: number): T {
  return Array.isArray(value) ? value[index] : value;
}

function rawDays(testCase: Case): RawDay[] {
  return testCase.weeks.flatMap((week) =>
    Array.from({ length: 7 }, (_, i) => ({
      date: addDays(week.start, i),
      goal_type: perDay(week.goal_type, i),
      target: perDay(week.target, i),
      planned: week.planned[i] === '1',
      paused: week.paused[i] === '1',
      done: week.done[i] === '1',
      value: week.value?.[i] ?? 0,
    })),
  );
}

describe('evaluate (shared cases)', () => {
  it('finds the shared cases', () => {
    expect(cases.length).toBeGreaterThan(10);
  });

  for (const testCase of cases) {
    it(testCase.name, () => {
      const result = evaluate(rawDays(testCase), testCase.today, testCase.start, testCase.end);
      expect(result.days.map((d) => d.state)).toEqual(testCase.expect.states);
      expect(result.quota).toEqual(testCase.expect.quota);
      expect(result.week).toEqual(testCase.expect.week);
    });
  }
});
