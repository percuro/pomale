import { describe, expect, it } from 'vitest';
import { addDays, belongsToDayBefore, dayEndTime, isBeforeDayEnd, todayIn, weekStart, weekdayIndex } from './dates';

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

  it('keeps the night in the day before until the day end', () => {
    // Wednesday 25 Nov: 00:59 and 01:00 in Vienna (UTC+1)
    expect(todayIn('Europe/Vienna', new Date('2026-11-24T23:59:00Z'), 1)).toBe('2026-11-24');
    expect(todayIn('Europe/Vienna', new Date('2026-11-25T00:00:00Z'), 1)).toBe('2026-11-25');
    expect(todayIn('Europe/Vienna', new Date('2026-11-24T23:00:00Z'), 0)).toBe('2026-11-25');
    expect(todayIn('Europe/Vienna', new Date('2026-11-25T04:59:00Z'), 6)).toBe('2026-11-24');
    expect(todayIn('Europe/Vienna', new Date('2026-11-24T22:59:00Z'), 6)).toBe('2026-11-24');
    // Monday night still belongs to the old week
    expect(weekStart(todayIn('Europe/Vienna', new Date('2026-11-29T23:30:00Z'), 1))).toBe('2026-11-23');
    expect(isBeforeDayEnd('Europe/Vienna', 1, new Date('2026-11-24T23:30:00Z'))).toBe(true);
    expect(isBeforeDayEnd('Europe/Vienna', 1, new Date('2026-11-25T00:00:00Z'))).toBe(false);
    expect(isBeforeDayEnd('Europe/Vienna', 0, new Date('2026-11-24T23:30:00Z'))).toBe(false);
  });

  it('handles clock changes inside the night like the server', () => {
    // New York, 8 Mar 2026: 01:59 EST is followed by 03:00 EDT
    expect(todayIn('America/New_York', new Date('2026-03-08T06:59:00Z'), 2)).toBe('2026-03-07');
    expect(todayIn('America/New_York', new Date('2026-03-08T07:00:00Z'), 2)).toBe('2026-03-08');
    // 1 Nov 2026: 01:30 happens twice, both still Saturday; 02:00 EST is Sunday
    expect(todayIn('America/New_York', new Date('2026-11-01T05:30:00Z'), 2)).toBe('2026-10-31');
    expect(todayIn('America/New_York', new Date('2026-11-01T06:30:00Z'), 2)).toBe('2026-10-31');
    expect(todayIn('America/New_York', new Date('2026-11-01T07:00:00Z'), 2)).toBe('2026-11-01');
  });

  it('names the day end and reminder times before it', () => {
    expect(dayEndTime(0)).toBe('00:00');
    expect(dayEndTime(6)).toBe('06:00');
    expect(belongsToDayBefore('00:30', 1)).toBe(true);
    expect(belongsToDayBefore('01:00', 1)).toBe(false);
    expect(belongsToDayBefore('00:30', 0)).toBe(false);
    expect(belongsToDayBefore('', 2)).toBe(false);
  });

  it('does calendar arithmetic without time zone drift', () => {
    expect(addDays('2026-03-28', 1)).toBe('2026-03-29');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(weekStart('2026-11-29')).toBe('2026-11-23');
    expect(weekdayIndex('2026-11-23')).toBe(0);
    expect(weekdayIndex('2026-11-29')).toBe(6);
  });
});
