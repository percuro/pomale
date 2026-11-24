/**
 * Local storage in IndexedDB: the queue of unsent changes and the last loaded day
 * lists. Without IndexedDB (e.g. some private modes) an in-memory store is used
 * that lasts until the app is closed.
 */
import { openDB, type DBSchema, type IDBPDatabase } from 'idb';

export interface ServerState {
  done: boolean;
  version: number;
  updated_at: string | null;
}

export interface QueuedOp {
  op_id: string;
  habit_id: number;
  date: string;
  done: boolean;
  /** Last known server version of the entry (0 = no entry yet) */
  base_version: number;
  created_at: number;
  /** The server has a different state meanwhile: the user must choose */
  conflict?: ServerState;
}

interface HabitDB extends DBSchema {
  queue: { key: string; value: QueuedOp };
  cache: { key: string; value: unknown };
}

let dbPromise: Promise<IDBPDatabase<HabitDB> | null> | null = null;
const memoryQueue = new Map<string, QueuedOp>();
const memoryCache = new Map<string, unknown>();

function db(): Promise<IDBPDatabase<HabitDB> | null> {
  if (!dbPromise) {
    dbPromise = openDB<HabitDB>('habit-tracker', 1, {
      upgrade(database) {
        database.createObjectStore('queue', { keyPath: 'op_id' });
        database.createObjectStore('cache');
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

export async function clearAll(): Promise<void> {
  const database = await db();
  if (database) {
    await database.clear('queue');
    await database.clear('cache');
  }
  memoryQueue.clear();
  memoryCache.clear();
}
