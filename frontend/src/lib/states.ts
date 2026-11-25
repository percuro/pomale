import type { DayState } from './types';

/** Text: t(`state.${state}`) */
export const STATE_ICON: Record<DayState, string> = {
  open: '○',
  done: '✓',
  extra_done: '+',
  not_planned: '–',
  future: '·',
  paused: '⏸',
  partial: '◐',
};
