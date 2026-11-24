/**
 * Queue for changes to days. Every change (online too) is stored locally first and
 * then sent: on app start, when returning to the app, on "online" and right after
 * the change. No Background Sync: iOS does not support it reliably for web apps.
 */
import { ApiError, apiFetch } from './api';
import { allOps, deleteOp, putOp, type QueuedOp, type ServerState } from './offline-store';
import type { CheckinResponse } from './types';

type Listener = () => void;

export interface SyncSnapshot {
  ops: QueuedOp[];
  syncing: boolean;
  lastError: string | null;
}

function newOpId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

class SyncEngine {
  private snapshot: SyncSnapshot = { ops: [], syncing: false, lastError: null };
  private listeners = new Set<Listener>();
  private running: Promise<void> | null = null;
  private rerun = false;
  /** Process changes one after another, even on a quick double tap */
  private chain: Promise<void> = Promise.resolve();
  private loaded: Promise<void> | null = null;
  onApplied: (response: CheckinResponse) => void = () => {};

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getSnapshot = () => this.snapshot;

  private emit(patch: Partial<SyncSnapshot>) {
    this.snapshot = { ...this.snapshot, ...patch };
    this.listeners.forEach((listener) => listener());
  }

  private async reload() {
    this.emit({ ops: await allOps() });
  }

  load(): Promise<void> {
    if (!this.loaded) this.loaded = this.reload();
    return this.loaded;
  }

  /** Set the target state of a day. knownVersion = version from the last server response. */
  setDay(habitId: number, date: string, done: boolean, knownVersion: number): Promise<void> {
    const next = this.chain.then(() => this.enqueue(habitId, date, done, knownVersion));
    this.chain = next.catch(() => {});
    return next;
  }

  private async enqueue(habitId: number, date: string, done: boolean, knownVersion: number) {
    await this.load();
    const existing = this.snapshot.ops.find((op) => op.habit_id === habitId && op.date === date);
    const op: QueuedOp = existing
      ? {
          ...existing,
          op_id: newOpId(),
          done,
          // Changing again during a conflict resolves it in favour of this device
          base_version: existing.conflict ? existing.conflict.version : existing.base_version,
          conflict: undefined,
        }
      : { op_id: newOpId(), habit_id: habitId, date, done, base_version: knownVersion, created_at: Date.now() };
    if (existing) await deleteOp(existing.op_id);
    await putOp(op);
    await this.reload();
    void this.flush();
  }

  async resolve(opId: string, keep: 'device' | 'server') {
    const op = this.snapshot.ops.find((candidate) => candidate.op_id === opId);
    if (!op?.conflict) return;
    await deleteOp(op.op_id);
    if (keep === 'device') {
      await putOp({ ...op, op_id: newOpId(), base_version: op.conflict.version, conflict: undefined });
    }
    await this.reload();
    void this.flush();
  }

  /** Send all pending changes. If a run is in progress, another one follows right after. */
  flush(): Promise<void> {
    if (this.running) {
      this.rerun = true;
      return this.running;
    }
    this.running = (async () => {
      await this.load();
      this.emit({ syncing: true });
      try {
        do {
          this.rerun = false;
          await this.sendPending();
        } while (this.rerun);
      } finally {
        this.running = null;
        this.emit({ syncing: false, ops: await allOps() });
      }
    })();
    return this.running;
  }

  private async sendPending(): Promise<void> {
    for (const { op_id } of await allOps()) {
      // re-read: changes may have been replaced or adjusted while sending
      const op = (await allOps()).find((candidate) => candidate.op_id === op_id);
      if (!op || op.conflict) continue;
      try {
        const response = await apiFetch<CheckinResponse>(`/v1/habits/${op.habit_id}/days/${op.date}`, {
          method: 'PUT',
          body: JSON.stringify({ done: op.done, op_id: op.op_id, base_version: op.base_version }),
        });
        await deleteOp(op.op_id);
        // A follow-up change to the same day made while sending (e.g. an immediate undo)
        // builds on this device's own change, so it takes over the new version
        for (const later of await allOps()) {
          if (later.habit_id === op.habit_id && later.date === op.date && later.base_version === op.base_version) {
            await putOp({ ...later, base_version: response.version });
          }
        }
        this.onApplied(response);
        this.emit({ lastError: null, ops: await allOps() });
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          const detail = error.detail as { server?: ServerState } | undefined;
          if ((await allOps()).some((candidate) => candidate.op_id === op.op_id)) {
            await putOp({ ...op, conflict: detail?.server ?? { done: !op.done, version: op.base_version + 1, updated_at: null } });
          }
          continue;
        }
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 429) {
          // Undeliverable (e.g. future date, habit deleted): drop it, but report it
          await deleteOp(op.op_id);
          this.emit({ lastError: `Nicht gespeichert: ${error.message}` });
          continue;
        }
        // Offline, server unreachable, logged out: retry later
        this.rerun = false;
        return;
      }
    }
  }

  reset() {
    this.loaded = null;
    this.emit({ ops: [], lastError: null });
  }
}

export const syncEngine = new SyncEngine();
