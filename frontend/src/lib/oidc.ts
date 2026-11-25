import { apiFetch } from './api';

/**
 * Start a sign-in at the OIDC provider: the API remembers the flow and answers with the
 * provider's URL; the browser leaves the app and comes back through /api/v1/auth/oidc/callback.
 */
export async function startOidc(path: string, body: Record<string, unknown>): Promise<void> {
  const { authorize_url } = await apiFetch<{ authorize_url: string }>(path, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  window.location.assign(authorize_url);
}

/** "error=oidc.no_account&reauth=ok" → {error: "oidc.no_account", reauth: "ok"}; the leading # is optional */
export function parseHashParams(hash: string): Record<string, string> {
  const params = new URLSearchParams(hash.replace(/^#/, ''));
  return Object.fromEntries(params.entries());
}

/**
 * Read what the OIDC callback put in the fragment (#error=…, #oidc=linked, #reauth=ok) once,
 * then remove it from the address bar so a reload does not show it again.
 */
export function takeHashParams(): Record<string, string> {
  const hash = window.location.hash;
  if (!hash) return {};
  const params = parseHashParams(hash);
  window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
  return params;
}
