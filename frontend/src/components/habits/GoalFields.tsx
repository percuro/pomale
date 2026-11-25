import { useId } from 'react';
import { useT } from '../../i18n/context';
import type { Goal } from '../../hooks/useHabits';
import type { GoalType } from '../../lib/types';
import { MAX_TARGET } from '../../lib/goals';
import { WeekdayPicker } from './WeekdayPicker';

const GOAL_TYPES: GoalType[] = ['days', 'weekly_count', 'quantity'];
const DEFAULT_TARGET: Record<GoalType, number | null> = { days: null, weekly_count: 3, quantity: 8 };

/** Goal type (days, n× a week, amount per day), its target and, where it applies, the weekdays. */
export function GoalFields({
  value,
  unit,
  onChange,
  onUnitChange,
}: {
  value: Goal;
  unit: string;
  onChange: (goal: Goal) => void;
  onUnitChange: (unit: string) => void;
}) {
  const t = useT();
  const name = useId();
  const setType = (goalType: GoalType) =>
    onChange({
      goal_type: goalType,
      target: goalType === value.goal_type ? value.target : DEFAULT_TARGET[goalType],
      weekdays: goalType === 'weekly_count' ? 127 : value.weekdays || 127,
    });

  return (
    <>
      <fieldset className="weekday-picker">
        <legend>{t('habits.goal')}</legend>
        <div className="chips" role="radiogroup">
          {GOAL_TYPES.map((goalType) => (
            <label key={goalType} className="chip">
              <input
                type="radio"
                name={name}
                checked={value.goal_type === goalType}
                onChange={() => setType(goalType)}
              />
              <span aria-hidden="true">{t(`habits.goal.${goalType}`)}</span>
              <span className="sr-only">{t(`habits.goal.${goalType}`)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {value.goal_type !== 'days' && (
        <div className="field-row">
          <label className="field">
            <span>{t(`habits.target.${value.goal_type}`)}</span>
            <input
              type="number"
              inputMode="numeric"
              required
              min={1}
              max={MAX_TARGET[value.goal_type]}
              value={value.target ?? ''}
              onChange={(e) => onChange({ ...value, target: e.target.value === '' ? null : Math.round(Number(e.target.value)) })}
            />
          </label>
          {value.goal_type === 'quantity' && (
            <label className="field">
              <span>{t('habits.unit')}</span>
              <input maxLength={20} value={unit} placeholder={t('habits.unitPlaceholder')} onChange={(e) => onUnitChange(e.target.value)} />
            </label>
          )}
        </div>
      )}
      {value.goal_type !== 'weekly_count' && (
        <WeekdayPicker value={value.weekdays} onChange={(weekdays) => onChange({ ...value, weekdays })} />
      )}
    </>
  );
}
