/**
 * Date arithmetic on ISO calendar days (YYYY-MM-DD), independent of the device time zone.
 * Names of days and months come from Intl in the UI language (src/i18n/core.ts).
 */

function parse(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function format(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  const date = parse(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return format(date);
}

/** 0 = Monday … 6 = Sunday */
export function weekdayIndex(iso: string): number {
  return (parse(iso).getUTCDay() + 6) % 7;
}

/** Weeks start on Monday in every language: the weekly quota is built on that. */
export function weekStart(iso: string): string {
  return addDays(iso, -weekdayIndex(iso));
}

/** The calendar day and the hour (0–23) on the clock of the given time zone. */
function clockIn(timeZone: string, now: Date): { day: string; hour: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  // Some engines write midnight as "24" despite h23
  return { day: `${get('year')}-${get('month')}-${get('day')}`, hour: Number(get('hour')) % 24 };
}

/**
 * Today's date in the given time zone (not the device's). With a day end after midnight
 * (e.g. 1), the hours before it still belong to the day before: the same rule as the server's
 * day_service.today_in, which only compares the clock hour.
 */
export function todayIn(timeZone: string, now: Date = new Date(), dayEndHour = 0): string {
  const { day, hour } = clockIn(timeZone, now);
  return hour < dayEndHour ? addDays(day, -1) : day;
}

/** True between midnight and a later day end: "today" is still the calendar day before. */
export function isBeforeDayEnd(timeZone: string, dayEndHour: number, now: Date = new Date()): boolean {
  return dayEndHour > 0 && clockIn(timeZone, now).hour < dayEndHour;
}

/** "01:00" for a day end hour, the same way reminder times are shown. */
export function dayEndTime(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`;
}

/** A reminder time ("00:30") before the day end belongs to the day before. */
export function belongsToDayBefore(time: string, dayEndHour: number): boolean {
  const hour = Number(time.slice(0, 2));
  return time.length >= 5 && Number.isFinite(hour) && hour < dayEndHour;
}
