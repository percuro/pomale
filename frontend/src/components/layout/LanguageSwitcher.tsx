import { useI18n } from '../../i18n/context';
import { LOCALES } from '../../i18n/core';

/** Language choice on pages without an account (login, setup, invitation). */
export function LanguageSwitcher() {
  const { locale, t, setDeviceLocale } = useI18n();
  return (
    <div className="language-switcher" role="group" aria-label={t('language.label')}>
      {LOCALES.map((option) => (
        <button
          key={option}
          type="button"
          className="link-button"
          lang={option}
          aria-pressed={locale === option}
          onClick={() => setDeviceLocale(option)}
        >
          {t(`language.${option}`)}
        </button>
      ))}
    </div>
  );
}
