import { useMemo } from 'react';
import { useT } from '../../i18n/context';

function allZones(): string[] {
  try {
    return Intl.supportedValuesOf('timeZone');
  } catch {
    return [];
  }
}

/** Time zone choice; '' = the server default. */
export function TimezoneSelect({
  value,
  serverDefault,
  onChange,
}: {
  value: string;
  serverDefault: string;
  onChange: (zone: string) => void;
}) {
  const t = useT();
  const zones = useMemo(() => {
    const list = allZones();
    return value && !list.includes(value) ? [value, ...list] : list;
  }, [value]);
  return (
    <label className="field">
      <span>{t('account.timezone')}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('account.timezoneDefault', { zone: serverDefault })}</option>
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone.replaceAll('_', ' ')}
          </option>
        ))}
      </select>
      <small className="subtle">{t('account.timezoneHint')}</small>
    </label>
  );
}
