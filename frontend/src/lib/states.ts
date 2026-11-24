import type { DayState } from './types';

/** Text: t(`state.${state}`) */
export const STATE_ICON: Record<DayState, string> = {
  open: '○',
  done: '✓',
  extra_done: '+',
  not_planned: '–',
  future: '·',
};

export function stateAfter(planned: boolean, done: boolean): DayState {
  if (done) return planned ? 'done' : 'extra_done';
  return planned ? 'open' : 'not_planned';
}
