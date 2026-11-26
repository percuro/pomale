/** Translation and locale-aware formatting without a library (see en.ts for the keys). */
import { ApiError } from '../lib/api';
import type { Locale } from '../lib/types';
import { de } from './de';
import { en, type MessageKey, type Messages } from './en';

export const LOCALES: readonly Locale[] = ['en', 'de'];
export const DEFAULT_LOCALE: Locale = 'en';
const CATALOGS: Record<Locale, Messages> = { en, de };

type PluralBase<K> = K extends `${infer Base}_other` ? Base : never;
type PluralForm<K> = K extends `${string}_one` | `${string}_other` ? K : never;
/** Keys to call t() with: plural keys without their _one/_other suffix */
export type TKey = Exclude<MessageKey, PluralForm<MessageKey>> | PluralBase<MessageKey>;
export type Params = Record<string, string | number>;
export type Translate = (key: TKey, params?: Params) => string;

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (LOCALES as readonly string[]).includes(value);
}

/** First supported language among the browser's preferences, e.g. de-AT → de. */
export function browserLocale(languages: readonly string[] = globalThis.navigator?.languages ?? []): Locale | null {
  for (const language of languages) {
    const base = language.toLowerCase().split('-')[0];
    if (isLocale(base)) return base;
  }
  return null;
}

function interpolate(text: string, params?: Params): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
}

export function createTranslate(locale: Locale): Translate {
  const messages = CATALOGS[locale];
  const plural = new Intl.PluralRules(locale);
  return (key, params) => {
    const forms = messages as Record<string, string>;
    if (!(key in forms) && params && typeof params.count === 'number') {
      const form = plural.select(params.count);
      const text = forms[`${key}_${form}`] ?? forms[`${key}_other`];
      return interpolate(text ?? key, params);
    }
    return interpolate(forms[key] ?? key, params);
  };
}

export function hasMessage(key: string): key is TKey {
  return key in en || `${key}_other` in en;
}

/** Translation of an API error code (e.g. "account.wrong_password"), or null if unknown. */
export function codeMessage(code: string | undefined, t: Translate, body?: Record<string, unknown>): string | null {
  const key = `error.${code ?? ''}`;
  if (!code || !hasMessage(key)) return null;
  const params: Params = {};
  for (const [name, value] of Object.entries(body ?? {})) {
    if (typeof value === 'string' || typeof value === 'number') params[name] = value;
  }
  return t(key, params);
}

/** User-facing text for any error: by the API's code where known, else a generic message. */
export function errorMessage(error: unknown, t: Translate): string {
  if (error instanceof ApiError) {
    return codeMessage(error.code, t, error.body) ?? t('error.http', { status: error.status });
  }
  if (error instanceof TypeError) return t('error.network');
  return t('error.unknown');
}

function parseIso(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

/** A known Monday, to name weekdays by index (0 = Monday … 6 = Sunday) */
const MONDAY = Date.UTC(2026, 10, 23);

export interface Formatters {
  /** "Tuesday, November 24" / "Dienstag, 24. November" */
  longDate(iso: string): string;
  /** "11/24" / "24.11." */
  shortDate(iso: string): string;
  /** "Nov 23 – 29, 2026" / "23.–29. Nov. 2026" */
  dateRange(startIso: string, endIso: string): string;
  /** 0 = Monday: "Mon" / "Mo" */
  weekdayShort(index: number): string;
  /** 0 = Monday: "Monday" / "Montag" */
  weekdayLong(index: number): string;
  /** A UTC timestamp from the API in the device's time zone, short date and time */
  dateTime(isoUtc: string | null): string;
  /** "daily", "on weekdays", "Mon, Wed" … for a weekday bit mask (bit 0 = Monday) */
  weekdays(mask: number): string;
  /** "November 2026" */
  monthYear(iso: string): string;
  /** 0.83 → "83%" / "83 %" */
  percent(ratio: number): string;
  /** A file size: "820 kB", "1.4 MB" */
  bytes(size: number): string;
}

export function createFormatters(locale: Locale, t: Translate): Formatters {
  const long = new Intl.DateTimeFormat(locale, { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });
  const short = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'numeric', timeZone: 'UTC' });
  const range = new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const dayShort = new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' });
  const dayLong = new Intl.DateTimeFormat(locale, { weekday: 'long', timeZone: 'UTC' });
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: 'short', timeStyle: 'short' });
  const month = new Intl.DateTimeFormat(locale, { month: 'long', year: 'numeric', timeZone: 'UTC' });
  const percent = new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 0 });
  const unit = (name: string) =>
    new Intl.NumberFormat(locale, { style: 'unit', unit: name, unitDisplay: 'short', maximumFractionDigits: 1 });
  const sizes = { byte: unit('byte'), kilobyte: unit('kilobyte'), megabyte: unit('megabyte') };
  const weekdayShort = (index: number) => dayShort.format(new Date(MONDAY + index * 86_400_000)).replace(/\.$/, '');
  return {
    longDate: (iso) => long.format(parseIso(iso)),
    shortDate: (iso) => short.format(parseIso(iso)),
    dateRange: (startIso, endIso) => range.formatRange(parseIso(startIso), parseIso(endIso)),
    weekdayShort,
    weekdayLong: (index) => dayLong.format(new Date(MONDAY + index * 86_400_000)),
    dateTime: (isoUtc) => {
      if (!isoUtc) return t('common.never');
      const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(isoUtc) ? isoUtc : `${isoUtc}Z`);
      return Number.isNaN(date.getTime()) ? '' : stamp.format(date);
    },
    weekdays: (mask) => {
      if (mask === 127) return t('weekdays.summary.daily');
      if (mask === 0b0011111) return t('weekdays.summary.weekdays');
      if (mask === 0b1100000) return t('weekdays.summary.weekend');
      return [0, 1, 2, 3, 4, 5, 6].filter((i) => mask & (1 << i)).map(weekdayShort).join(', ');
    },
    monthYear: (iso) => month.format(parseIso(iso)),
    percent: (ratio) => percent.format(ratio),
    bytes: (size) =>
      size < 1000
        ? sizes.byte.format(size)
        : size < 1_000_000
          ? sizes.kilobyte.format(size / 1000)
          : sizes.megabyte.format(size / 1_000_000),
  };
}
