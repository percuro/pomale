import { useI18n } from '../../i18n/context';
import type { TKey } from '../../i18n/core';

const PRESETS: [TKey, number][] = [
  ['weekdays.preset.daily', 127],
  ['weekdays.preset.weekdays', 0b0011111],
  ['weekdays.preset.weekend', 0b1100000],
];

export function WeekdayPicker({
  value,
  onChange,
  legend,
}: {
  value: number;
  onChange: (mask: number) => void;
  legend?: string;
}) {
  const { t, format } = useI18n();
  return (
    <fieldset className="weekday-picker">
      <legend>{legend ?? t('weekdays.legend')}</legend>
      <div className="chips">
        {[0, 1, 2, 3, 4, 5, 6].map((i) => {
          const bit = 1 << i;
          return (
            <label key={i} className="choice">
              <input
                type="checkbox"
                checked={Boolean(value & bit)}
                onChange={(e) => onChange(e.target.checked ? value | bit : value & ~bit)}
              />
              <span aria-hidden="true">{format.weekdayShort(i)}</span>
              <span className="sr-only">{format.weekdayLong(i)}</span>
            </label>
          );
        })}
      </div>
      <div className="presets">
        {PRESETS.map(([label, mask]) => (
          <button
            key={label}
            type="button"
            className="link-button"
            aria-pressed={value === mask}
            onClick={() => onChange(mask)}
          >
            {t(label)}
          </button>
        ))}
      </div>
      {value === 0 && <p className="error" role="alert">{t('weekdays.pickOne')}</p>}
    </fieldset>
  );
}
