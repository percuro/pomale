import { describe, expect, it } from 'vitest';
import { normalizeTimes, sameTimes, timesValid } from './reminder-times';

describe('reminder times', () => {
  it('normalizes', () => {
    expect(normalizeTimes(['20:00', '', '07:30:00', '07:30'])).toEqual(['07:30', '20:00']);
  });

  it('validates', () => {
    expect(timesValid([])).toBe(true);
    expect(timesValid(['07:30', ''])).toBe(true);
    expect(timesValid(['07:30', '07:30'])).toBe(false);
    expect(timesValid(['7:30'])).toBe(false);
    expect(timesValid(['24:00'])).toBe(false);
    expect(timesValid(['07:00', '08:00', '09:00', '10:00'])).toBe(false);
  });

  it('compares regardless of order and empty inputs', () => {
    expect(sameTimes(['20:00', '07:30'], ['07:30', '20:00', ''])).toBe(true);
    expect(sameTimes(['07:30'], ['07:31'])).toBe(false);
  });
});
