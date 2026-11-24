import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeServer, type FakeServer } from '../test/fake-server';
import { clearAll } from './offline-store';
import { overlay } from './overlay';
import { syncEngine } from './sync-engine';
import type { DaysResponse } from './types';

const TODAY = '2026-11-24';
let server: FakeServer;

function serverDays(habitId: number, date: string): DaysResponse {
  const s = server.state.get(`${habitId}:${date}`) ?? { done: false, version: 0 };
  return {
    today: TODAY,
    timezone: 'UTC',
    start: date,
    end: date,
    habits: [
      {
        id: habitId,
        name: 'Lesen',
        cue: null,
        archived: false,
        quota: { done: 0, due: 0 },
        days: [{ date, planned: true, done: s.done, state: s.done ? 'done' : 'open', version: s.version }],
      },
    ],
  };
}

beforeEach(async () => {
  server = createFakeServer(TODAY);
  vi.stubGlobal('fetch', server.fetch);
  await clearAll();
  syncEngine.reset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.stubGlobal('window', new EventTarget());
});

/** setDay while offline and wait for its background flush attempt. */
async function setOffline(habitId: number, date: string, done: boolean, known: number) {
  server.offline = true;
  await syncEngine.setDay(habitId, date, done, known);
  await syncEngine.flush();
}

describe('sync engine', () => {
  it('buffers changes while offline and marks them as pending', async () => {
    await setOffline(1, TODAY, true, 0);
    const ops = syncEngine.getSnapshot().ops;
    expect(ops).toHaveLength(1);
    const shown = overlay(serverDays(1, TODAY), ops, TODAY).habits[0].days[0];
    expect(shown).toMatchObject({ done: true, state: 'done', pending: true });
    expect(server.state.size).toBe(0);
  });

  it('sends pending changes once online again', async () => {
    await setOffline(1, TODAY, true, 0);
    server.offline = false;
    await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`1:${TODAY}`)).toEqual({ done: true, version: 1 });
  });

  it('treats an unchanged target state as success', async () => {
    server.set(1, TODAY, true);
    await setOffline(1, TODAY, false, 1);
    await syncEngine.setDay(1, TODAY, true, 1);
    server.offline = false;
    await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`1:${TODAY}`)).toEqual({ done: true, version: 1 });
  });

  it('reports a conflict instead of overwriting a newer server change', async () => {
    server.set(1, TODAY, true); // v1, known to this device
    await setOffline(1, TODAY, false, 1);
    server.offline = false;
    server.set(1, TODAY, false); // other device: v2
    server.set(1, TODAY, true); // other device: v3
    await syncEngine.flush();
    const [op] = syncEngine.getSnapshot().ops;
    expect(op.conflict).toEqual({ done: true, version: 3, updated_at: null });
    expect(server.state.get(`1:${TODAY}`)).toEqual({ done: true, version: 3 });
    const shown = overlay(serverDays(1, TODAY), syncEngine.getSnapshot().ops, TODAY).habits[0].days[0];
    expect(shown.conflict).toBe(true);
  });

  it('applies the device state after the user chooses it', async () => {
    server.set(1, TODAY, true);
    await setOffline(1, TODAY, false, 1);
    server.offline = false;
    server.set(1, TODAY, false);
    server.set(1, TODAY, true);
    await syncEngine.flush();
    await syncEngine.resolve(syncEngine.getSnapshot().ops[0].op_id, 'device');
    await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`1:${TODAY}`)).toEqual({ done: false, version: 4 });
  });

  it('keeps the server state when the user chooses it', async () => {
    server.set(1, TODAY, true);
    await setOffline(1, TODAY, false, 1);
    server.offline = false;
    server.set(1, TODAY, false);
    server.set(1, TODAY, true);
    await syncEngine.flush();
    await syncEngine.resolve(syncEngine.getSnapshot().ops[0].op_id, 'server');
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`1:${TODAY}`)).toEqual({ done: true, version: 3 });
  });

  it('keeps an offline entry on its original day when synced after midnight', async () => {
    await setOffline(1, TODAY, true, 0);
    server.today = '2026-11-25';
    server.offline = false;
    await syncEngine.flush();
    expect(server.requests.at(-1)?.date).toBe(TODAY);
    expect(server.state.get(`1:${TODAY}`)?.done).toBe(true);
    expect(server.state.has('1:2026-11-25')).toBe(false);
  });

  it('drops undeliverable changes and reports them', async () => {
    await syncEngine.setDay(1, '2026-11-30', true, 0);
    await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(syncEngine.getSnapshot().lastError).toMatch(/Zukünftige/);
  });

  it('does not report a false conflict when undo follows while the first request is in flight', async () => {
    server.delayMs = 20;
    await Promise.all([syncEngine.setDay(2, TODAY, true, 0), syncEngine.setDay(2, TODAY, false, 0)]);
    for (let i = 0; i < 10 && syncEngine.getSnapshot().ops.length; i++) await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`2:${TODAY}`)?.done ?? false).toBe(false);
  });

  it('sends every request with op_id and base_version', async () => {
    await syncEngine.setDay(1, TODAY, true, 0);
    await syncEngine.flush();
    expect(server.requests[0].body).toMatchObject({ done: true, base_version: 0 });
    expect(typeof server.requests[0].body.op_id).toBe('string');
  });
});
