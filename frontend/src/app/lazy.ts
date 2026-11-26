import type { ComponentType } from 'react';

const RELOADED_KEY = 'pomale.chunkReload';

/**
 * Loads the chunk of a page. After an update the server only has the new chunks; a page that
 * was opened before (and not yet taken over by the new service worker) reloads once to get them.
 */
export async function loadChunk<T>(load: () => Promise<T>): Promise<T> {
  try {
    const module = await load();
    storage(() => window.sessionStorage.removeItem(RELOADED_KEY));
    return module;
  } catch (error) {
    if (storage(() => window.sessionStorage.getItem(RELOADED_KEY)) === null) {
      storage(() => window.sessionStorage.setItem(RELOADED_KEY, '1'));
      window.location.reload();
      return new Promise<T>(() => {});
    }
    throw error;
  }
}

/** A route whose page is its own chunk: `lazy: lazyPage(() => import('…'), (m) => m.Page)`. */
export function lazyPage<T>(load: () => Promise<T>, pick: (module: T) => ComponentType) {
  return async () => ({ Component: pick(await loadChunk(load)) });
}

function storage<T>(access: () => T): T | 'unavailable' {
  // Private windows and blocked site data: without storage a second attempt cannot be told
  // apart, so there is no automatic reload; the error page offers one
  try {
    return access();
  } catch {
    return 'unavailable';
  }
}
