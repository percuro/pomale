import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeServer, type FakeServer } from '../test/fake-server';
import { allOps, clearAll, putOp } from './offline-store';
import { overlay } from './overlay';
import { syncEngine } from './sync-engine';
import type { DaysResponse } from './types';

const TODAY = '2026-11-24';
const ALEX = { id: 1, username: 'alex' };
const SAM = { id: 2, username: 'sam' };
let server: FakeServer;

function serverDays(habitId: number, date: string): DaysResponse {
  const s = server.state.get(`${habitId}:${date}`) ?? { done: false, version: 0 };
  return {
    today: TODAY,
    timezone: 'UTC',
    start: date,
    end: date,
    groups: [],
    habits: [
      {
        id: habitId,
        name: 'Lesen',
        cue: null,
        archived: false,
        goal_type: 'days',
        target: null,
        unit: null,
        color: null,
        group_id: null,
        week: null,
        quota: { done: 0, due: 0 },
        days: [
          {
            date,
            planned: true,
            done: s.done,
            state: s.done ? 'done' : 'open',
            version: s.version,
            goal_type: 'days',
            target: null,
            paused: false,
            value: null,
            note: null,
          },
        ],
      },
    ],
  };
}

beforeEach(async () => {
  server = createFakeServer(TODAY);
  vi.stubGlobal('fetch', server.fetch);
  await clearAll();
  syncEngine.reset();
  syncEngine.setOwner(ALEX);
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
    expect(syncEngine.getSnapshot().lastError).toEqual({
      code: 'checkin.future_day',
      message: 'Future days cannot be checked off',
    });
  });

  it('does not report a false conflict when undo follows while the first request is in flight', async () => {
    server.delayMs = 20;
    await Promise.all([syncEngine.setDay(2, TODAY, true, 0), syncEngine.setDay(2, TODAY, false, 0)]);
    for (let i = 0; i < 10 && syncEngine.getSnapshot().ops.length; i++) await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(server.state.get(`2:${TODAY}`)?.done ?? false).toBe(false);
  });

  it('keeps another account\'s changes queued until it logs in again', async () => {
    await setOffline(1, TODAY, true, 0);
    server.offline = false;
    syncEngine.setOwner(SAM);
    await syncEngine.flush();
    expect(server.requests).toHaveLength(0);
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
    expect(await allOps()).toHaveLength(1);

    await syncEngine.setDay(7, TODAY, true, 0);
    await syncEngine.flush();
    expect(server.requests.map((r) => r.habitId)).toEqual([7]);

    syncEngine.setOwner(ALEX);
    await syncEngine.flush();
    expect(server.requests.map((r) => r.habitId)).toEqual([7, 1]);
    expect(await allOps()).toHaveLength(0);
  });

  it('shows only the signed-in account\'s pending changes', async () => {
    await setOffline(1, TODAY, true, 0);
    syncEngine.setOwner(SAM);
    await syncEngine.load();
    await setOffline(7, TODAY, true, 0);
    expect(syncEngine.getSnapshot().ops.map((op) => [op.habit_id, op.user_id])).toEqual([[7, 2]]);
    syncEngine.setOwner(null);
    await syncEngine.flush();
    expect(syncEngine.getSnapshot().ops).toHaveLength(0);
  });

  it('sends a change queued before 0.4 only as the account cached back then', async () => {
    await putOp({ op_id: 'old', habit_id: 3, date: TODAY, done: true, base_version: 0, created_at: 1, user_id: null, username: 'alex' });
    syncEngine.setOwner(SAM);
    await syncEngine.flush();
    expect(server.requests).toHaveLength(0);
    syncEngine.setOwner(ALEX);
    await syncEngine.flush();
    expect(server.requests.map((r) => r.habitId)).toEqual([3]);
    expect(await allOps()).toHaveLength(0);
  });

  it('sends every request with op_id and base_version', async () => {
    await syncEngine.setDay(1, TODAY, true, 0);
    await syncEngine.flush();
    expect(server.requests[0].body).toMatchObject({ done: true, base_version: 0 });
    expect(typeof server.requests[0].body.op_id).toBe('string');
  });

  it('sends amounts as absolute values and merges quick taps into one change', async () => {
    server.quantity.add(5);
    server.offline = true;
    for (const value of [1, 2, 3]) await syncEngine.setDay(5, TODAY, { value }, 0);
    expect(syncEngine.getSnapshot().ops).toHaveLength(1);
    expect(syncEngine.getSnapshot().ops[0]).toMatchObject({ value: 3, done: true, base_version: 0 });
    server.offline = false;
    await syncEngine.flush();
    expect(server.requests.map((r) => r.body)).toEqual([expect.objectContaining({ value: 3, base_version: 0 })]);
    expect(server.requests[0].body).not.toHaveProperty('done');
    expect(server.state.get(`5:${TODAY}`)).toMatchObject({ value: 3, version: 1 });
  });

  it('reports a conflict for an amount changed on another device', async () => {
    server.quantity.add(5);
    server.state.set(`5:${TODAY}`, { done: true, version: 1, value: 4 });
    await syncEngine.setDay(5, TODAY, { value: 2 }, 0);
    await syncEngine.flush();
    const [op] = syncEngine.getSnapshot().ops;
    expect(op.conflict).toMatchObject({ version: 1, value: 4 });
    await syncEngine.resolve(op.op_id, 'device');
    await syncEngine.flush();
    expect(server.state.get(`5:${TODAY}`)).toMatchObject({ value: 2, version: 2 });
  });

  it('still sends a change queued before 0.6 without a value as done', async () => {
    await putOp({ op_id: 'v05', habit_id: 4, date: TODAY, done: true, base_version: 0, created_at: 1, user_id: 1 });
    await syncEngine.flush();
    expect(server.requests[0].body).toMatchObject({ done: true });
    expect(server.requests[0].body).not.toHaveProperty('value');
  });
});

