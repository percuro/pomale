import { Link } from 'react-router-dom';
import { usePushConfig, usePushDevices } from '../../hooks/usePush';
import { useSession } from '../../hooks/useSession';
import { useT } from '../../i18n/context';
import { belongsToDayBefore } from '../../lib/dates';
import { REMINDERS_MAX, timesValid } from '../../lib/reminder-times';

/** Up to three local times at which to remind if the habit is still open. */
export function ReminderTimes({ value, onChange }: { value: string[]; onChange: (times: string[]) => void }) {
  const t = useT();
  const { me } = useSession();
  const dayEndHour = me.day_end_hour ?? 0;
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
      {value.map((time, index) => {
        const dayBefore = belongsToDayBefore(time, dayEndHour);
        const noteId = `reminder-day-before-${index}`;
        return (
          <div className="field-row" key={index}>
            <div className="field-stack">
              <input
                type="time"
                step={60}
                value={time}
                aria-label={t('reminders.timeLabel', { n: index + 1 })}
                aria-describedby={dayBefore ? noteId : undefined}
                onChange={(e) => set(index, e.target.value)}
              />
              {/* Before the day end the reminder is about the day that is ending */}
              {dayBefore && <small id={noteId} className="subtle">{t('reminders.dayBefore')}</small>}
            </div>
            <button
              type="button"
              className="button"
              aria-label={t('reminders.removeLabel', { n: index + 1 })}
              onClick={() => onChange(value.filter((_, i) => i !== index))}
            >
              {t('reminders.remove')}
            </button>
          </div>
        );
      })}
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
