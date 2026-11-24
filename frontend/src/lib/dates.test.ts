import { describe, expect, it } from 'vitest';
import { addDays, todayIn, weekStart, weekdayIndex, weekdaysLabel } from './dates';

describe('dates', () => {
  it('computes today in the given time zone, not the device zone', () => {
    const lateUtc = new Date('2026-11-24T23:30:00Z');
    expect(todayIn('UTC', lateUtc)).toBe('2026-11-24');
    expect(todayIn('Europe/Vienna', lateUtc)).toBe('2026-11-25');
    expect(todayIn('America/New_York', lateUtc)).toBe('2026-11-24');
  });

  it('handles daylight saving time changes', () => {
    expect(todayIn('Europe/Vienna', new Date('2026-03-28T22:59:00Z'))).toBe('2026-03-28');
    expect(todayIn('Europe/Vienna', new Date('2026-03-28T23:00:00Z'))).toBe('2026-03-29');
    expect(todayIn('Europe/Vienna', new Date('2026-10-24T22:00:00Z'))).toBe('2026-10-25');
    expect(todayIn('Europe/Vienna', new Date('2026-10-25T22:59:00Z'))).toBe('2026-10-25');
  });

  it('does calendar arithmetic without time zone drift', () => {
    expect(addDays('2026-03-28', 1)).toBe('2026-03-29');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(weekStart('2026-11-29')).toBe('2026-11-23');
    expect(weekdayIndex('2026-11-23')).toBe(0);
    expect(weekdayIndex('2026-11-29')).toBe(6);
  });

  it('labels weekday masks', () => {
    expect(weekdaysLabel(127)).toBe('täglich');
    expect(weekdaysLabel(0b0011111)).toBe('werktags');
    expect(weekdaysLabel(0b0000101)).toBe('Mo, Mi');
  });
});
