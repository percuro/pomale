/** Date arithmetic on ISO calendar days (YYYY-MM-DD), independent of the device time zone. */

const WEEKDAY_SHORT = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'];
const WEEKDAY_LONG = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];
const MONTHS = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

export { WEEKDAY_SHORT, WEEKDAY_LONG };

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

export function weekStart(iso: string): string {
  return addDays(iso, -weekdayIndex(iso));
}

export function shortDate(iso: string): string {
  const date = parse(iso);
  return `${date.getUTCDate()}.${date.getUTCMonth() + 1}.`;
}

export function longDate(iso: string): string {
  const date = parse(iso);
  return `${WEEKDAY_LONG[weekdayIndex(iso)]}, ${date.getUTCDate()}. ${MONTHS[date.getUTCMonth()]}`;
}

/** Today's date in the given time zone (not the device's). */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? '';
  return `${get('year')}-${get('month')}-${get('day')}`;
}

export function weekdaysLabel(mask: number): string {
  if (mask === 127) return 'täglich';
  if (mask === 0b0011111) return 'werktags';
  if (mask === 0b1100000) return 'am Wochenende';
  return WEEKDAY_SHORT.filter((_, i) => mask & (1 << i)).join(', ');
}
