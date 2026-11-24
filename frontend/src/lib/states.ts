import type { DayState } from './types';

export const STATE_LABEL: Record<DayState, string> = {
  open: 'Offen',
  done: 'Erledigt',
  extra_done: 'Zusätzlich erledigt',
  not_planned: 'Nicht geplant',
  future: 'Noch nicht',
};

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
