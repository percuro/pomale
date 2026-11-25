import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { DAYS_KEY } from '../../hooks/useDays';
import { HISTORY_KEY } from '../../hooks/useHistory';
import { isWorkerMessage } from '../../lib/notification-actions';
import { syncEngine } from '../../lib/sync-engine';

/** Reacts to the service worker: a habit checked off from a notification, or a tap on one. */
export function WorkerBridge() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    const container = typeof navigator !== 'undefined' ? navigator.serviceWorker : undefined;
    if (!container) return;
    const onMessage = (event: MessageEvent) => {
      const message = event.data;
      if (!isWorkerMessage(message)) return;
      if (message.type === 'pomale:checked-off') {
        void queryClient.invalidateQueries({ queryKey: DAYS_KEY });
        void queryClient.invalidateQueries({ queryKey: HISTORY_KEY });
      } else if (message.type === 'pomale:queued') {
        void syncEngine.refresh();
      } else if (message.type === 'pomale:navigate') {
        navigate(message.url);
      }
    };
    container.addEventListener('message', onMessage);
    return () => container.removeEventListener('message', onMessage);
  }, [queryClient, navigate]);

  return null;
}
