/**
 * Local storage in IndexedDB: the queue of unsent changes and the last loaded day
 * lists. Without IndexedDB (e.g. some private modes) an in-memory store is used
 * that lasts until the app is closed.
 *
 * Several accounts can use the same device: every queued change records its account,
 * and cached day lists are keyed by account (see daysCacheKey).
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

export interface ServerState {
  done: boolean;
  version: number;
  updated_at: string | null;
  /** quantity goals */
  value?: number | null;
}

export interface QueuedOp {
  op_id: string;
  habit_id: number;
  date: string;
  done: boolean;
  /** Quantity goals: the amount to set (sent instead of `done`); missing in changes queued before 0.6 */
  value?: number;
  /** Last known server version of the entry (0 = no entry yet) */
  base_version: number;
  created_at: number;
  /** The account that made the change; null for changes queued before 0.4 (see `username`) */
  user_id: number | null;
  /** Owner of a change queued before 0.4, taken from the cached account at upgrade */
  username?: string | null;
  /** The server has a different state meanwhile: the user must choose */
  conflict?: ServerState;
}

/** Who is logged in, as far as the queue is concerned */
export interface QueueOwner {
  id: number;
  username: string;
}

export function belongsTo(op: QueuedOp, owner: QueueOwner | null): boolean {
  if (!owner) return false;
  if (op.user_id != null) return op.user_id === owner.id;
  // Queued before 0.4: owned by the account that was cached then (or unknown: one account per device back then)
  return op.username == null || op.username === owner.username;
}

interface HabitDB extends DBSchema {
  queue: { key: string; value: QueuedOp };
  cache: { key: string; value: unknown };
}

const DB_NAME = 'habit-tracker';
const DB_VERSION = 3;

let dbPromise: Promise<IDBPDatabase<HabitDB> | null> | null = null;
const memoryQueue = new Map<string, QueuedOp>();
const memoryCache = new Map<string, unknown>();

function db(): Promise<IDBPDatabase<HabitDB> | null> {
  if (!dbPromise) {
    dbPromise = openDB<HabitDB>(DB_NAME, DB_VERSION, {
      async upgrade(database, oldVersion, _newVersion, transaction) {
        if (oldVersion < 1) {
          database.createObjectStore('queue', { keyPath: 'op_id' });
          database.createObjectStore('cache');
        }
        if (oldVersion === 1) {
          // 0.3 → 0.4: give queued changes their owner (the account cached at that time)
          const cachedMe = (await transaction.objectStore('cache').get('me')) as { username?: string } | undefined;
          const queue = transaction.objectStore('queue');
          for (const op of await queue.getAll()) {
            await queue.put({ ...op, user_id: null, username: cachedMe?.username ?? null });
          }
        }
        if (oldVersion >= 1 && oldVersion < 3) {
          // Day lists were cached without an account (0.3) or without the fields of 0.6
          // (goal type, target, value); drop them, they are reloaded
          const cache = transaction.objectStore('cache');
          for (const key of await cache.getAllKeys()) {
            if (String(key).startsWith('days:')) await cache.delete(key);
          }
        }
      },
    }).catch(() => null);
  }
  return dbPromise;
}

export async function allOps(): Promise<QueuedOp[]> {
  const database = await db();
  const ops = database ? await database.getAll('queue') : [...memoryQueue.values()];
  return ops.sort((a, b) => a.created_at - b.created_at);
}

export async function putOp(op: QueuedOp): Promise<void> {
  const database = await db();
  if (database) await database.put('queue', op);
  else memoryQueue.set(op.op_id, op);
}

export async function deleteOp(opId: string): Promise<void> {
  const database = await db();
  if (database) await database.delete('queue', opId);
  else memoryQueue.delete(opId);
}

export async function cacheGet<T>(key: string): Promise<T | undefined> {
  const database = await db();
  return (database ? await database.get('cache', key) : memoryCache.get(key)) as T | undefined;
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  const database = await db();
  if (database) await database.put('cache', value, key);
  else memoryCache.set(key, value);
}

export function daysCacheKey(userId: number, from: string, to: string): string {
  return `days:${userId}:${from}:${to}`;
}

/**
 * Forget what belongs to the signed-in account on this device (account, day lists) while
 * keeping unsent changes: they are sent when their account logs in again.
 * `keepUserId`: keep that account's day lists (e.g. right after it logged in).
 */
export async function clearAccountCache(keepUserId?: number): Promise<void> {
  const keep = keepUserId === undefined ? null : `days:${keepUserId}:`;
  const database = await db();
  const keys = database ? await database.getAllKeys('cache') : [...memoryCache.keys()];
  for (const key of keys.map(String)) {
    if (key === 'me' && keepUserId !== undefined) continue;
    if (keep && key.startsWith(keep)) continue;
    if (database) await database.delete('cache', key);
    else memoryCache.delete(key);
  }
}

export async function clearAll(): Promise<void> {
  const database = await db();
  if (database) {
    await database.clear('queue');
    await database.clear('cache');
  }
  memoryQueue.clear();
  memoryCache.clear();
}

/** Tests only: close the connection so the next access opens (and upgrades) the database again. */
export async function closeForTests(): Promise<void> {
  const database = await dbPromise;
  database?.close();
  dbPromise = null;
}
