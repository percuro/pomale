import { describe, expect, it, vi } from 'vitest';
import { checkOff, notificationOptions, parsePayload, type ReminderHabit } from './notification-actions';
import type { QueuedOp } from './offline-store';

const habit: ReminderHabit = { id: 7, date: '2026-11-24', version: 2, user: 1 };

function deps(fetchImpl: typeof fetch) {
  const queued: QueuedOp[] = [];
  return {
    queued,
    deps: {
      fetch: fetchImpl,
      putOp: async (op: QueuedOp) => {
        queued.push(op);
      },
      newOpId: () => 'op-1',
      now: () => 1000,
    },
  };
}

describe('parsePayload', () => {
  it('reads a reminder', () => {
    const payload = parsePayload(
      JSON.stringify({ title: 'Lesen', body: 'Noch offen', tag: 'reminder-7', url: '/today', habit, done_label: 'Erledigt' }),
    );
    expect(payload).toEqual({ title: 'Lesen', body: 'Noch offen', tag: 'reminder-7', url: '/today', habit, done_label: 'Erledigt' });
  });

  it('falls back on anything unreadable', () => {
    for (const text of [null, '', 'not json', '[]', '{"title": 5}']) {
      const payload = parsePayload(text);
      expect(payload.url).toBe('/today');
      expect(payload.habit).toBeNull();
      expect(payload.title).toBe('pomale');
    }
  });

  it('only opens paths inside the app', () => {
    for (const url of ['https://evil.example', '//evil.example', 'javascript:alert(1)']) {
      expect(parsePayload(JSON.stringify({ title: 'x', url })).url).toBe('/today');
    }
    expect(parsePayload(JSON.stringify({ title: 'x', url: '/account' })).url).toBe('/account');
  });

  it('drops a malformed habit', () => {
    const payload = parsePayload(JSON.stringify({ title: 'x', habit: { id: '7', date: 'today', version: 0, user: 1 } }));
    expect(payload.habit).toBeNull();
  });
});

describe('notificationOptions', () => {
  it('offers the done button only with a habit and a label', () => {
    const base = parsePayload(JSON.stringify({ title: 'Lesen', habit, done_label: 'Erledigt' }));
    expect(notificationOptions(base).actions).toEqual([{ action: 'done', title: 'Erledigt' }]);
    expect(notificationOptions({ ...base, habit: null }).actions).toEqual([]);
    expect(notificationOptions(base).data).toBe(base);
  });
});

describe('checkOff', () => {
  it('sets the day like the offline queue does', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    const { deps: d, queued } = deps(fetchMock as unknown as typeof fetch);
    expect(await checkOff(habit, d)).toBe('done');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/v1/habits/7/days/2026-11-24');
    expect(init.method).toBe('PUT');
    expect((init.headers as Record<string, string>)['X-Habit-CSRF']).toBe('1');
    expect(JSON.parse(init.body as string)).toEqual({ done: true, op_id: 'op-1', base_version: 2 });
    expect(queued).toEqual([]);
  });

  it('queues the change when offline', async () => {
    const { deps: d, queued } = deps((async () => {
      throw new TypeError('Failed to fetch');
    }) as unknown as typeof fetch);
    expect(await checkOff(habit, d)).toBe('queued');
    expect(queued).toEqual([
      { op_id: 'op-1', habit_id: 7, date: '2026-11-24', done: true, base_version: 2, created_at: 1000, user_id: 1 },
    ]);
  });

  it('opens the app when the server refuses', async () => {
    for (const status of [401, 409, 404, 500]) {
      const { deps: d, queued } = deps((async () => new Response('{}', { status })) as unknown as typeof fetch);
      expect(await checkOff(habit, d)).toBe('open');
      expect(queued).toEqual([]);
    }
  });
});
