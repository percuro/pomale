/// <reference lib="webworker" />
/**
 * Service worker: caches the app shell (like the generated one before 0.7) and shows reminders.
 * API responses never come from this cache; day lists and the change queue live in IndexedDB.
 */
import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import {
  checkOff,
  notificationOptions,
  parsePayload,
  type PushPayload,
  type WorkerMessage,
} from './lib/notification-actions';
import { putOp } from './lib/offline-store';

declare let self: ServiceWorkerGlobalScope;

// registerType "autoUpdate": a new version takes over at once
self.skipWaiting();
clientsClaim();

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }));

const API_HEADERS = { 'Content-Type': 'application/json', 'X-Habit-CSRF': '1' };

function newOpId(): string {
  return self.crypto.randomUUID();
}

async function windows(): Promise<readonly WindowClient[]> {
  return self.clients.matchAll({ type: 'window', includeUncontrolled: true });
}

async function tell(message: WorkerMessage): Promise<void> {
  for (const client of await windows()) client.postMessage(message);
}

/** Bring an open window to the front (and to `url`), or open a new one */
async function openApp(url: string): Promise<void> {
  const open = (await windows()).find((client) => new URL(client.url).origin === self.location.origin);
  if (open) {
    await open.focus();
    open.postMessage({ type: 'pomale:navigate', url } satisfies WorkerMessage);
    return;
  }
  await self.clients.openWindow(url);
}

self.addEventListener('push', (event) => {
  const payload = parsePayload(event.data?.text());
  event.waitUntil(self.registration.showNotification(payload.title, notificationOptions(payload)));
});

self.addEventListener('notificationclick', (event) => {
  const payload = event.notification.data as PushPayload | undefined;
  event.notification.close();
  event.waitUntil(
    (async () => {
      const habit = payload?.habit;
      if (event.action === 'done' && habit) {
        const outcome = await checkOff(habit, { fetch: self.fetch.bind(self), putOp, newOpId, now: Date.now });
        if (outcome === 'done') return tell({ type: 'pomale:checked-off', habitId: habit.id, date: habit.date });
        if (outcome === 'queued') return tell({ type: 'pomale:queued' });
      }
      await openApp(payload?.url ?? '/today');
    })(),
  );
});

interface SubscriptionChangeEvent extends ExtendableEvent {
  readonly oldSubscription: PushSubscription | null;
  readonly newSubscription: PushSubscription | null;
}

// The browser renewed the subscription (Firefox does this now and then): tell the server
self.addEventListener('pushsubscriptionchange', (event) => {
  const change = event as SubscriptionChangeEvent;
  change.waitUntil(
    (async () => {
      let subscription = change.newSubscription;
      if (!subscription) {
        const config = await fetch('/api/v1/push/config', { credentials: 'same-origin' });
        if (!config.ok) return;
        const { public_key: key } = (await config.json()) as { public_key: string | null };
        if (!key) return;
        subscription = await self.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: key,
        });
      }
      await fetch('/api/v1/push/subscriptions', {
        method: 'POST',
        credentials: 'same-origin',
        headers: API_HEADERS,
        body: JSON.stringify({ ...subscription.toJSON(), old_endpoint: change.oldSubscription?.endpoint }),
      });
    })(),
  );
});
