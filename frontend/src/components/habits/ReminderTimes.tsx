import { Link } from 'react-router-dom';
import { usePushConfig, usePushDevices } from '../../hooks/usePush';
import { useT } from '../../i18n/context';
import { REMINDERS_MAX, timesValid } from '../../lib/reminder-times';

/** Up to three local times at which to remind if the habit is still open. */
export function ReminderTimes({ value, onChange }: { value: string[]; onChange: (times: string[]) => void }) {
  const t = useT();
  const config = usePushConfig();
  const enabled = config.data?.enabled === true;
  const devices = usePushDevices(enabled);
  if (!enabled) return null;
  const set = (index: number, time: string) => onChange(value.map((old, i) => (i === index ? time : old)));
  const noDevice = value.some(Boolean) && devices.isSuccess && devices.data.length === 0;

  return (
    <fieldset className="weekday-picker">
      <legend>{t('reminders.label')}</legend>
      {value.length === 0 && <p className="subtle">{t('reminders.none')}</p>}
      {value.map((time, index) => (
        <div className="field-row" key={index}>
          <input
            type="time"
            step={60}
            value={time}
            aria-label={t('reminders.timeLabel', { n: index + 1 })}
            onChange={(e) => set(index, e.target.value)}
          />
          <button
            type="button"
            className="button"
            aria-label={t('reminders.removeLabel', { n: index + 1 })}
            onClick={() => onChange(value.filter((_, i) => i !== index))}
          >
            {t('reminders.remove')}
          </button>
        </div>
      ))}
      {!timesValid(value) && <p className="error" role="alert">{t('reminders.invalid')}</p>}
      {value.length < REMINDERS_MAX && (
        <div className="button-row">
          <button type="button" className="button" onClick={() => onChange([...value, ''])}>
            {t('reminders.add')}
          </button>
        </div>
      )}
      {noDevice && (
        <p className="subtle">
          {t('reminders.noDevice')} <Link to="/account#reminders-heading">{t('reminders.toAccount')}</Link>
        </p>
      )}
    </fieldset>
  );
}
