/**
 * What the service worker does with reminders: show them, and check a habit off from the
 * notification's "done" button. Kept free of service-worker globals so Vitest can test it.
 */
import type { QueuedOp } from './offline-store';

/** The single habit of a reminder that offers a "done" button (see backend reminder_service) */
export interface ReminderHabit {
  id: number;
  date: string;
  /** Version of that day's entry when the reminder was sent (0 = none) */
  version: number;
  user: number;
}

export interface PushPayload {
  title: string;
  body: string;
  tag: string;
  url: string;
  habit: ReminderHabit | null;
  done_label?: string;
}

export const FALLBACK_TITLE = 'pomale';

/** Never throws: a push that cannot be read still has to show something (Safari requires it). */
export function parsePayload(text: string | null | undefined): PushPayload {
  const fallback: PushPayload = { title: FALLBACK_TITLE, body: '', tag: 'pomale', url: '/today', habit: null };
  if (!text) return fallback;
  try {
    const data = JSON.parse(text) as Partial<PushPayload>;
    const habit = data.habit;
    const validHabit =
      habit && Number.isInteger(habit.id) && /^\d{4}-\d{2}-\d{2}$/.test(habit.date) && Number.isInteger(habit.version)
        ? habit
        : null;
    return {
      title: typeof data.title === 'string' && data.title ? data.title : fallback.title,
      body: typeof data.body === 'string' ? data.body : '',
      tag: typeof data.tag === 'string' && data.tag ? data.tag : fallback.tag,
      // Only paths inside the app: a payload never sends the user elsewhere
      url: typeof data.url === 'string' && data.url.startsWith('/') && !data.url.startsWith('//') ? data.url : '/today',
      habit: validHabit,
      done_label: typeof data.done_label === 'string' ? data.done_label : undefined,
    };
  } catch {
    return fallback;
  }
}

export function notificationOptions(payload: PushPayload): NotificationOptions & { actions?: { action: string; title: string }[] } {
  return {
    body: payload.body,
    tag: payload.tag,
    icon: '/icon-192.png',
    badge: '/badge-96.png',
    data: payload,
    // Android and desktop show buttons; iOS ignores them and opens the app on tap
    actions: payload.habit && payload.done_label ? [{ action: 'done', title: payload.done_label }] : [],
  };
}

export type CheckOffOutcome = 'done' | 'queued' | 'open';

export interface CheckOffDeps {
  fetch: typeof fetch;
  putOp: (op: QueuedOp) => Promise<void>;
  newOpId: () => string;
  now: () => number;
}

/**
 * Check the reminder's habit off for the reminder's day.
 * done: the server took it. queued: offline, it waits in the app's queue (sent when the app
 * opens). open: anything else (logged out, changed meanwhile): the app should open instead.
 */
export async function checkOff(habit: ReminderHabit, deps: CheckOffDeps): Promise<CheckOffOutcome> {
  const opId = deps.newOpId();
  let response: Response;
  try {
    response = await deps.fetch(`/api/v1/habits/${habit.id}/days/${habit.date}`, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-Habit-CSRF': '1' },
      body: JSON.stringify({ done: true, op_id: opId, base_version: habit.version }),
    });
  } catch {
    try {
      await deps.putOp({
        op_id: opId,
        habit_id: habit.id,
        date: habit.date,
        done: true,
        base_version: habit.version,
        created_at: deps.now(),
        user_id: habit.user,
      });
      return 'queued';
    } catch {
      return 'open';
    }
  }
  return response.ok ? 'done' : 'open';
}

/** Messages from the service worker to open app windows */
export type WorkerMessage =
  | { type: 'pomale:checked-off'; habitId: number; date: string }
  | { type: 'pomale:queued' }
  | { type: 'pomale:navigate'; url: string };

export function isWorkerMessage(data: unknown): data is WorkerMessage {
  return typeof data === 'object' && data !== null && typeof (data as { type?: unknown }).type === 'string'
    && (data as { type: string }).type.startsWith('pomale:');
}
