/** Reminder times on a habit: up to three local times "HH:MM" (see backend REMINDERS_MAX). */
export const REMINDERS_MAX = 3;

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Valid, distinct times in order; empty inputs are dropped. `<input type="time">` may add seconds. */
export function normalizeTimes(values: string[]): string[] {
  const times = values.map((value) => value.trim().slice(0, 5)).filter((value) => TIME.test(value));
  return [...new Set(times)].sort();
}

/** True when every non-empty input is a time and none repeats */
export function timesValid(values: string[]): boolean {
  const filled = values.map((value) => value.trim()).filter(Boolean);
  return filled.length <= REMINDERS_MAX && normalizeTimes(filled).length === filled.length;
}

export function sameTimes(a: string[], b: string[]): boolean {
  const left = normalizeTimes(a);
  const right = normalizeTimes(b);
  return left.length === right.length && left.every((value, index) => value === right[index]);
}
