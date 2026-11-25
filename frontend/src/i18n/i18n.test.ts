/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../lib/api';
import { browserLocale, createFormatters, createTranslate, errorMessage, hasMessage } from './core';
import { de } from './de';
import { en } from './en';

const SRC = join(import.meta.dirname, '..');
const BACKEND = join(SRC, '..', '..', 'backend', 'app');

function files(dir: string, pattern: RegExp): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path, pattern);
    return pattern.test(name) ? [path] : [];
  });
}

describe('translations', () => {
  it('have the same keys in both languages', () => {
    expect(Object.keys(de).sort()).toEqual(Object.keys(en).sort());
  });

  it('use the same placeholders in both languages', () => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(placeholders(de[key]), key).toEqual(placeholders(en[key]));
    }
  });

  it('cover every error code the backend can return', () => {
    const codes = new Set<string>();
    for (const file of files(BACKEND, /\.py$/)) {
      const source = readFileSync(file, 'utf8');
      for (const match of source.matchAll(/(?:AppError|error_response)\(\s*\d+,\s*"([a-z_.]+)"/g)) codes.add(match[1]);
      // OIDC callback errors travel in the URL fragment (/login#error=<code>)
      for (const match of source.matchAll(/(?:OidcFlowError|OidcError)\(\s*"([a-z_.]+)"/g)) codes.add(match[1]);
      for (const match of source.matchAll(/"(oidc\.[a-z_]+)"/g)) codes.add(match[1]);
    }
    expect(codes.size).toBeGreaterThan(25);
    const missing = [...codes].filter((code) => !hasMessage(`error.${code}`));
    expect(missing).toEqual([]);
  });

  it('leave no German text in the components (all texts live in src/i18n)', () => {
    const german = /[äöüÄÖÜß]|\b(Gewohnheit|Abmelden|Anmelden|Passwort|Woche|Heute|Konto|Einladung|erledigt|nicht)\b/;
    const checked = files(SRC, /\.tsx?$/)
      .map((file) => relative(SRC, file))
      .filter((file) => !file.startsWith('i18n') && !file.startsWith('test') && !file.endsWith('.test.ts'));
    expect(checked).toContain(join('pages', 'TodayPage.tsx'));
    const offenders = checked
      .map((file) => join(SRC, file))
      .flatMap((file) =>
        readFileSync(file, 'utf8')
          .split('\n')
          .map((line, index) => ({ file, line: index + 1, text: line }))
          .filter(({ text }) => german.test(text)),
      );
    expect(offenders).toEqual([]);
  });
});

describe('translate', () => {
  it('fills placeholders and picks plural forms', () => {
    const tDe = createTranslate('de');
    const tEn = createTranslate('en');
    expect(tEn('today.progress', { done: 2, total: 3 })).toBe('2 of 3 done');
    expect(tDe('sync.waiting', { count: 1 })).toBe('1 Änderung wartet auf Übertragung.');
    expect(tDe('sync.waiting', { count: 3 })).toBe('3 Änderungen warten auf Übertragung.');
    expect(tEn('sync.waiting', { count: 0 })).toBe('0 changes are waiting to be sent.');
  });

  it('translates API errors by code, with their parameters', () => {
    const t = createTranslate('de');
    const tooShort = new ApiError('The password needs at least 12 characters', 422, 'account.password_too_short', {
      detail: '…',
      code: 'account.password_too_short',
      min_length: 12,
    });
    expect(errorMessage(tooShort, t)).toBe('Das Passwort braucht mindestens 12 Zeichen.');
    expect(errorMessage(new ApiError('<html>Bad gateway', 502), t)).toBe('Der Server meldet einen Fehler (502).');
    expect(errorMessage(new TypeError('Failed to fetch'), t)).toBe('Keine Verbindung zum Server');
  });
});

describe('formatters', () => {
  const de_ = createFormatters('de', createTranslate('de'));
  const en_ = createFormatters('en', createTranslate('en'));

  it('name days in the UI language, weeks start on Monday', () => {
    expect(de_.longDate('2026-11-24')).toBe('Dienstag, 24. November');
    expect(en_.longDate('2026-11-24')).toBe('Tuesday, November 24');
    expect([0, 6].map(de_.weekdayShort)).toEqual(['Mo', 'So']);
    expect([0, 6].map(en_.weekdayShort)).toEqual(['Mon', 'Sun']);
    expect(de_.shortDate('2026-11-24')).toBe('24.11.');
  });

  it('describe weekday plans', () => {
    expect(de_.weekdays(127)).toBe('täglich');
    expect(en_.weekdays(0b0011111)).toBe('on weekdays');
    expect(de_.weekdays(0b0000101)).toBe('Mo, Mi');
    expect(en_.weekdays(0b0000101)).toBe('Mon, Wed');
  });

  it('show API timestamps (UTC without zone) in local time', () => {
    expect(en_.dateTime(null)).toBe('never');
    expect(en_.dateTime('2026-11-24T10:00:00')).toBe(en_.dateTime('2026-11-24T10:00:00Z'));
  });
});

describe('browser language', () => {
  it('takes the first supported one', () => {
    expect(browserLocale(['fr-FR', 'de-AT', 'en'])).toBe('de');
    expect(browserLocale(['en-US'])).toBe('en');
    expect(browserLocale(['fr', 'it'])).toBeNull();
  });
});
