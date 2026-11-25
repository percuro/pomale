import { useId } from 'react';
import { useT } from '../../i18n/context';
import { HABIT_COLORS, type HabitColor } from '../../lib/types';

/** Radio group of the fixed palette; every option is named, the colour is only a hint. */
export function ColorPicker({ value, onChange }: { value: HabitColor | null; onChange: (color: HabitColor | null) => void }) {
  const t = useT();
  const name = useId();
  return (
    <fieldset className="weekday-picker">
      <legend>{t('habits.color')}</legend>
      <div className="chips">
        {[null, ...HABIT_COLORS].map((color) => (
          <label key={color ?? 'none'} className="chip color-chip">
            <input type="radio" name={name} checked={value === color} onChange={() => onChange(color)} />
            <span aria-hidden="true">
              <span className="swatch" style={color ? { background: `var(--habit-${color})` } : undefined} />
              {t(color ? `habits.color.${color}` : 'habits.color.none')}
            </span>
            <span className="visually-hidden">{t(color ? `habits.color.${color}` : 'habits.color.none')}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
