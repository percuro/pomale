import type { CSSProperties } from 'react';
import type { DayState } from '../../lib/types';
import { CheckIcon, PlusIcon } from '../Icons';

/**
 * The state of a day as a ring: empty when open, partly filled with the amount inside,
 * filled with a check when done. Decoration only: the state is always written or named
 * next to it (t(`state.${state}`)).
 */
export function StateIcon({ state, value, target }: { state: DayState; value?: number | null; target?: number | null }) {
  if (state === 'partial') {
    const share = target && target > 0 ? Math.min(100, Math.round(((value ?? 0) / target) * 100)) : 50;
    return (
      <span className="state-icon ring" style={{ '--p': share } as CSSProperties} aria-hidden="true">
        <span>{value ?? ''}</span>
      </span>
    );
  }
  return (
    <span className={`state-icon is-${state}`} aria-hidden="true">
      {state === 'done' && <CheckIcon />}
      {state === 'extra_done' && <PlusIcon />}
      {state === 'paused' && <span className="pause-bars" />}
    </span>
  );
}
