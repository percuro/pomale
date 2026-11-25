import type { CSSProperties } from 'react';
import type { HabitColor } from './types';

/** The habit's colour as a CSS variable (a stripe next to its name; never the only hint). */
export function colorStyle(color: HabitColor | null): CSSProperties | undefined {
  return color ? ({ '--habit-color': `var(--habit-${color})` } as CSSProperties) : undefined;
}

/** Group habits into the account's groups (in their order), then those without a group. */
export function byGroup<T extends { group_id: number | null }>(
  items: T[],
  groups: { id: number; name: string }[],
): { id: number | null; name: string | null; items: T[] }[] {
  const sections = groups
    .map((group) => ({ id: group.id as number | null, name: group.name as string | null, items: items.filter((i) => i.group_id === group.id) }))
    .filter((section) => section.items.length > 0);
  const known = new Set(groups.map((g) => g.id));
  const rest = items.filter((i) => i.group_id === null || !known.has(i.group_id));
  if (rest.length) sections.push({ id: null, name: null, items: rest });
  return sections;
}
