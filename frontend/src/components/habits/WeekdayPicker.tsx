import { WEEKDAY_LONG, WEEKDAY_SHORT } from '../../lib/dates';

const PRESETS: [string, number][] = [
  ['Täglich', 127],
  ['Werktags', 0b0011111],
  ['Wochenende', 0b1100000],
];

export function WeekdayPicker({
  value,
  onChange,
  legend = 'Geplante Tage',
}: {
  value: number;
  onChange: (mask: number) => void;
  legend?: string;
}) {
  return (
    <fieldset className="weekday-picker">
      <legend>{legend}</legend>
      <div className="chips">
        {WEEKDAY_SHORT.map((label, i) => {
          const bit = 1 << i;
          return (
            <label key={label} className="chip">
              <input
                type="checkbox"
                checked={Boolean(value & bit)}
                onChange={(e) => onChange(e.target.checked ? value | bit : value & ~bit)}
              />
              <span aria-hidden="true">{label}</span>
              <span className="visually-hidden">{WEEKDAY_LONG[i]}</span>
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
            {label}
          </button>
        ))}
      </div>
      {value === 0 && <p className="error" role="alert">Mindestens einen Tag wählen.</p>}
    </fieldset>
  );
}
