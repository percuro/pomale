const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

/** Error body of the API: {detail, code} plus optional extra fields (e.g. `server` on a 409). */
export interface ApiErrorBody {
  detail?: unknown;
  code?: string;
  [key: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  /** Stable machine-readable code, e.g. "auth.invalid_credentials"; translate by this */
  readonly code?: string;
  readonly body?: ApiErrorBody;

  constructor(message: string, status: number, code?: string, body?: ApiErrorBody) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.body = body;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set('X-Habit-CSRF', '1');
  if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });

  if (response.status === 401) {
    window.dispatchEvent(new Event('habit:unauthorized'));
  }

  if (!response.ok) {
    const errorText = await response.text();
    let errorMessage = errorText || `HTTP ${response.status}`;
    let body: ApiErrorBody | undefined;
    try {
      body = JSON.parse(errorText) as ApiErrorBody;
      if (typeof body.detail === 'string') {
        errorMessage = body.detail;
      }
    } catch {
      // Not every error response is JSON (e.g. a proxy error page); keep the raw text.
    }
    throw new ApiError(errorMessage, response.status, typeof body?.code === 'string' ? body.code : undefined, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
