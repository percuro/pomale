/**
 * Queue for changes to days. Every change (online too) is stored locally first and
 * then sent: on app start, when returning to the app, on "online" and right after
 * the change. No Background Sync: iOS does not support it reliably for web apps.
 *
 * Only the signed-in account's changes are shown and sent. Changes of other accounts
 * on the same device stay queued until that account logs in again.
 */
import { ApiError, apiFetch } from './api';
import { allOps, belongsTo, deleteOp, putOp, type QueueOwner, type QueuedOp, type ServerState } from './offline-store';
import type { CheckinResponse } from './types';

type Listener = () => void;

/** What to set on a day: checked off or not, or an amount for quantity goals */
export type DayChange = { done: boolean } | { value: number };

/** A change the server refused; `code` is translated in the UI */
export interface SyncError {
  code?: string;
  message: string;
}

export interface SyncSnapshot {
  /** Changes of the signed-in account */
  ops: QueuedOp[];
  syncing: boolean;
  lastError: SyncError | null;
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
  private owner: QueueOwner | null = null;
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

  /** Switch to the signed-in account (null: nobody). Other accounts' changes stay queued. */
  setOwner(owner: QueueOwner | null) {
    if (owner?.id === this.owner?.id && owner?.username === this.owner?.username) return;
    this.owner = owner;
    this.loaded = null;
    this.emit({ ops: [], lastError: null });
    void this.load();
  }

  private async mine(): Promise<QueuedOp[]> {
    return (await allOps()).filter((op) => belongsTo(op, this.owner));
  }

  private async reload() {
    this.emit({ ops: await this.mine() });
  }

  load(): Promise<void> {
    if (!this.loaded) this.loaded = this.reload();
    return this.loaded;
  }

  /**
   * Set the target state of a day: `done`, or `{ value }` for quantity goals (an absolute
   * amount, never "+1", so repeating it is harmless). knownVersion = version from the last
   * server response. Quick taps on the same day replace each other in the queue.
   */
  setDay(habitId: number, date: string, change: boolean | DayChange, knownVersion: number): Promise<void> {
    const normalized: DayChange = typeof change === 'boolean' ? { done: change } : change;
    const next = this.chain.then(() => this.enqueue(habitId, date, normalized, knownVersion));
    this.chain = next.catch(() => {});
    return next;
  }

  private async enqueue(habitId: number, date: string, change: DayChange, knownVersion: number) {
    const done = 'value' in change ? change.value > 0 : change.done;
    const value = 'value' in change ? change.value : undefined;
    await this.load();
    const owner = this.owner;
    if (!owner) throw new Error('setDay without a signed-in account');
    const existing = this.snapshot.ops.find((op) => op.habit_id === habitId && op.date === date);
    const op: QueuedOp = existing
      ? {
          ...existing,
          op_id: newOpId(),
          done,
          value,
          // Changing again during a conflict resolves it in favour of this device
          base_version: existing.conflict ? existing.conflict.version : existing.base_version,
          conflict: undefined,
        }
      : {
          op_id: newOpId(),
          habit_id: habitId,
          date,
          done,
          value,
          base_version: knownVersion,
          created_at: Date.now(),
          user_id: owner.id,
        };
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
        this.emit({ syncing: false, ops: await this.mine() });
      }
    })();
    return this.running;
  }

  private async sendPending(): Promise<void> {
    const owner = this.owner;
    if (!owner) return;
    for (const { op_id } of await this.mine()) {
      // re-read: changes may have been replaced or adjusted while sending, or the account switched
      if (this.owner !== owner) return;
      let op = (await this.mine()).find((candidate) => candidate.op_id === op_id);
      if (!op || op.conflict) continue;
      if (op.user_id == null) {
        // Queued before 0.4: from now on it belongs to this account by id
        op = { ...op, user_id: owner.id, username: undefined };
        await putOp(op);
      }
      try {
        const response = await apiFetch<CheckinResponse>(`/v1/habits/${op.habit_id}/days/${op.date}`, {
          method: 'PUT',
          body: JSON.stringify({
            ...(op.value !== undefined ? { value: op.value } : { done: op.done }),
            op_id: op.op_id,
            base_version: op.base_version,
          }),
        });
        await deleteOp(op.op_id);
        // A follow-up change to the same day made while sending (e.g. an immediate undo)
        // builds on this device's own change, so it takes over the new version
        for (const later of await this.mine()) {
          if (later.habit_id === op.habit_id && later.date === op.date && later.base_version === op.base_version) {
            await putOp({ ...later, base_version: response.version });
          }
        }
        this.onApplied(response);
        this.emit({ lastError: null, ops: await this.mine() });
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          const server = error.body?.server as ServerState | undefined;
          const current = op;
          if ((await allOps()).some((candidate) => candidate.op_id === current.op_id)) {
            await putOp({ ...current, conflict: server ?? { done: !current.done, version: current.base_version + 1, updated_at: null } });
          }
          continue;
        }
        if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 429) {
          // Undeliverable (e.g. future date, habit deleted): drop it, but report it
          await deleteOp(op.op_id);
          this.emit({ lastError: { code: error.code, message: error.message } });
          continue;
        }
        // Offline, server unreachable, logged out: retry later
        this.rerun = false;
        return;
      }
    }
  }

  /** Tests: forget the in-memory state (the stored queue is untouched) */
  reset() {
    this.loaded = null;
    this.owner = null;
    this.emit({ ops: [], lastError: null });
  }
}

export const syncEngine = new SyncEngine();
