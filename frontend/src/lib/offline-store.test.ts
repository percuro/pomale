import { deleteDB, openDB } from 'idb';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { allOps, cacheGet, cacheSet, clearAccountCache, closeForTests, daysCacheKey, putOp } from './offline-store';

const TODAY = '2026-11-24';

beforeEach(async () => {
  await closeForTests();
  await deleteDB('habit-tracker');
});

afterEach(async () => {
  await closeForTests();
});

describe('offline store', () => {
  it('upgrades a 0.3 database: queued changes keep their account, day lists are dropped', async () => {
    const v1 = await openDB('habit-tracker', 1, {
      upgrade(database) {
        database.createObjectStore('queue', { keyPath: 'op_id' });
        database.createObjectStore('cache');
      },
    });
    await v1.put('queue', { op_id: 'a', habit_id: 1, date: TODAY, done: true, base_version: 0, created_at: 1 });
    await v1.put('cache', { username: 'alex', today: TODAY, timezone: 'UTC' }, 'me');
    await v1.put('cache', { habits: [] }, `days:${TODAY}:${TODAY}`);
    v1.close();

    const [op] = await allOps();
    expect(op).toMatchObject({ op_id: 'a', user_id: null, username: 'alex' });
    expect(await cacheGet(`days:${TODAY}:${TODAY}`)).toBeUndefined();
    expect(await cacheGet('me')).toMatchObject({ username: 'alex' });
  });

  it('forgets account data on logout but keeps unsent changes', async () => {
    await putOp({ op_id: 'a', habit_id: 1, date: TODAY, done: true, base_version: 0, created_at: 1, user_id: 1 });
    await cacheSet('me', { id: 1 });
    await cacheSet(daysCacheKey(1, TODAY, TODAY), { habits: [] });
    await cacheSet(daysCacheKey(2, TODAY, TODAY), { habits: [] });

    await clearAccountCache(2);
    expect(await cacheGet(daysCacheKey(1, TODAY, TODAY))).toBeUndefined();
    expect(await cacheGet(daysCacheKey(2, TODAY, TODAY))).toBeDefined();
    expect(await cacheGet('me')).toBeDefined();

    await clearAccountCache();
    expect(await cacheGet(daysCacheKey(2, TODAY, TODAY))).toBeUndefined();
    expect(await cacheGet('me')).toBeUndefined();
    expect(await allOps()).toHaveLength(1);
  });
});
