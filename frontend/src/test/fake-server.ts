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
  state: Map<string, { done: boolean; version: number }>;
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
      if (!match || init?.method !== 'PUT') return json(404, { detail: 'Not found' });
      const habitId = Number(match[1]);
      const date = match[2];
      const body = JSON.parse(String(init.body)) as { done: boolean; base_version?: number; op_id?: string };
      server.requests.push({ habitId, date, body });
      if (date > server.today) return json(422, { detail: 'Zukünftige Tage können nicht erfasst werden' });
      const key = `${habitId}:${date}`;
      const current = server.state.get(key) ?? { done: false, version: 0 };
      const read = (s: { done: boolean; version: number }) => ({
        habit_id: habitId,
        date,
        done: s.done,
        state: s.done ? 'done' : 'open',
        version: s.version,
      });
      if (current.done === body.done) return json(200, read(current));
      if (body.base_version !== undefined && body.base_version !== current.version) {
        return json(409, {
          detail: { message: 'conflict', server: { done: current.done, version: current.version, updated_at: null } },
        });
      }
      const next = { done: body.done, version: current.version + 1 };
      server.state.set(key, next);
      return json(200, read(next));
    }) as typeof fetch,
  };
  return server;
}
