const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
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
    let errorMessage = errorText || `HTTP-Fehler ${response.status}`;
    let errorDetail: unknown;
    try {
      const parsed = JSON.parse(errorText) as { detail?: unknown };
      errorDetail = parsed.detail;
      if (typeof parsed.detail === 'string') {
        errorMessage = parsed.detail;
      } else if (Array.isArray(parsed.detail)) {
        errorMessage = 'Eingabe ungültig';
      }
    } catch {
      // Not every error response is JSON; keep the raw text in that case.
    }
    throw new ApiError(errorMessage, response.status, errorDetail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return 'Keine Verbindung zum Server';
  return 'Unbekannter Fehler';
}
