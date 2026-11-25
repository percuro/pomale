/**
 * In-memory stand-in for PUT /v1/habits/{id}/days/{date} with the same rules as the
 * backend (checkin_service.set_state): same target state = success, matching
 * base_version = apply, otherwise 409 with the server state; future dates = 422.
 */
export interface FakeServer {
  fetch: typeof fetch;
  offline: boolean;
  delayMs: number;
  today: string;
  /** value: quantity goals (habits listed in `quantity`) */
  state: Map<string, { done: boolean; version: number; value?: number }>;
  /** habit ids that are quantity goals: they take `value` */
  quantity: Set<number>;
  requests: { habitId: number; date: string; body: Record<string, unknown> }[];
  /** Change a day directly, like another device would. */
  set(habitId: number, date: string, done: boolean): void;
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

export function createFakeServer(today = '2026-11-24'): FakeServer {
  const server: FakeServer = {
    offline: false,
    delayMs: 0,
    today,
    state: new Map(),
    quantity: new Set(),
    requests: [],
    set(habitId, date, done) {
      const key = `${habitId}:${date}`;
      const current = this.state.get(key) ?? { done: false, version: 0 };
      if (current.done !== done) this.state.set(key, { done, version: current.version + 1 });
    },
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      if (server.offline) throw new TypeError('Failed to fetch');
      if (server.delayMs) await new Promise((resolve) => setTimeout(resolve, server.delayMs));
      if (server.offline) throw new TypeError('Failed to fetch');
      const url = String(input);
      const match = url.match(/\/v1\/habits\/(\d+)\/days\/(\d{4}-\d{2}-\d{2})$/);
      if (!match || init?.method !== 'PUT') return json(404, { detail: 'Not found', code: 'http.404' });
      const habitId = Number(match[1]);
      const date = match[2];
      const body = JSON.parse(String(init.body)) as {
        done?: boolean;
        value?: number;
        base_version?: number;
        op_id?: string;
      };
      server.requests.push({ habitId, date, body });
      if (date > server.today) return json(422, { detail: 'Future days cannot be checked off', code: 'checkin.future_day' });
      const key = `${habitId}:${date}`;
      const current = server.state.get(key) ?? { done: false, version: 0 };
      const quantity = server.quantity.has(habitId);
      if (body.value !== undefined && !quantity) {
        return json(422, { detail: 'Only quantity goals take a value', code: 'checkin.value_not_allowed' });
      }
      const read = (s: { done: boolean; version: number; value?: number }) => ({
        habit_id: habitId,
        date,
        done: s.done,
        state: s.done ? 'done' : 'open',
        version: s.version,
        value: quantity ? (s.value ?? 0) : null,
      });
      const wanted = quantity ? (body.value ?? (body.done ? 1 : 0)) : body.done;
      const now = quantity ? (current.value ?? 0) : current.done;
      if (now === wanted) return json(200, read(current));
      if (body.base_version !== undefined && body.base_version !== current.version) {
        return json(409, {
          detail: 'conflict',
          code: 'checkin.conflict',
          server: {
            done: current.done,
            version: current.version,
            updated_at: null,
            ...(quantity ? { value: current.value ?? 0 } : {}),
          },
        });
      }
      const next = quantity
        ? { done: Number(wanted) > 0, version: current.version + 1, value: Number(wanted) }
        : { done: Boolean(body.done), version: current.version + 1 };
      server.state.set(key, next);
      return json(200, read(next));
    }) as typeof fetch,
  };
  return server;
}
