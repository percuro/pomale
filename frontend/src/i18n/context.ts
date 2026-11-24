import { createContext, useContext } from 'react';
import type { Locale } from '../lib/types';
import { errorMessage, type Formatters, type Translate } from './core';

export interface I18n {
  locale: Locale;
  t: Translate;
  format: Formatters;
  /** The account's language (null = not set: the device choice or browser decides) */
  setAccountLocale(locale: Locale | null): void;
  /** Choice on this device (signed-out pages); stored in localStorage */
  setDeviceLocale(locale: Locale): void;
}

export const I18nContext = createContext<I18n | null>(null);

export function useI18n(): I18n {
  const i18n = useContext(I18nContext);
  if (!i18n) throw new Error('useI18n outside I18nProvider');
  return i18n;
}

/** Shorthand for the translate function */
export function useT(): Translate {
  return useI18n().t;
}

/** (error) → translated message, see errorMessage */
export function useErrorText(): (error: unknown) => string {
  const t = useT();
  return (error) => errorMessage(error, t);
}
