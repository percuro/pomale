import { useT } from '../../i18n/context';
import { dayEndTime } from '../../lib/dates';

/** The latest day end; must match DAY_END_HOUR_MAX on the server */
export const DAY_END_HOUR_MAX = 6;

/** When the account's day ends: midnight, or a full hour up to 06:00 for night owls. */
export function DayEndSelect({ value, onChange }: { value: number; onChange: (hour: number) => void }) {
  const t = useT();
  const hours = Array.from({ length: DAY_END_HOUR_MAX + 1 }, (_, hour) => hour);
  return (
    <label className="field">
      <span>{t('account.dayEnd')}</span>
      <select value={value} onChange={(event) => onChange(Number(event.target.value))}>
        {hours.map((hour) => (
          <option key={hour} value={hour}>
            {hour === 0 ? t('account.dayEndMidnight') : dayEndTime(hour)}
          </option>
        ))}
      </select>
      <small className="subtle">{t('account.dayEndHint')}</small>
    </label>
  );
}
