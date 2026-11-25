import { useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Locale } from '../lib/types';
import { browserLocale, createFormatters, createTranslate, DEFAULT_LOCALE, isLocale } from './core';
import { I18nContext, type I18n } from './context';

const STORAGE_KEY = 'pomale.locale';

function storedLocale(): Locale | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return isLocale(value) ? value : null;
  } catch {
    return null;
  }
}

/** Language: the account's setting, else this device's choice, else the browser's, else English. */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [accountLocale, setAccountLocale] = useState<Locale | null>(null);
  const [deviceLocale, setDeviceLocaleState] = useState<Locale | null>(storedLocale);
  const locale = accountLocale ?? deviceLocale ?? browserLocale() ?? DEFAULT_LOCALE;

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<I18n>(() => {
    const t = createTranslate(locale);
    return {
      locale,
      t,
      format: createFormatters(locale, t),
      setAccountLocale,
      setDeviceLocale: (next) => {
        setDeviceLocaleState(next);
        try {
          window.localStorage.setItem(STORAGE_KEY, next);
        } catch {
          // Private mode without storage: the choice lasts until the page is closed
        }
      },
    };
  }, [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
