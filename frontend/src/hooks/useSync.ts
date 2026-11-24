import { useSyncExternalStore } from 'react';
import { syncEngine } from '../lib/sync-engine';

export function useSync() {
  return useSyncExternalStore(syncEngine.subscribe, syncEngine.getSnapshot);
}
