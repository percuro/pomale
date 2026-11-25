/**
 * Web Push in the browser: can this device get reminders, and turning them on or off.
 * Reminders need a service worker, the Push API and permission for notifications. On iPhone
 * and iPad (iOS 16.4+) that exists only in the web app added to the home screen.
 */
import { apiFetch } from './api';
import type { PushDevice } from './types';

export type PushSupport = 'supported' | 'unsupported' | 'ios-needs-install';
export type PushState = 'unsupported' | 'ios-needs-install' | 'denied' | 'off' | 'on';

/** The parts of the browser this module looks at; tests pass their own */
export interface PushEnvironment {
  userAgent: string;
  platform: string;
  maxTouchPoints: number;
  /** navigator.standalone (iOS) or display-mode: standalone */
  standalone: boolean;
  hasServiceWorker: boolean;
  hasPushManager: boolean;
  hasNotification: boolean;
}

export function browserEnvironment(): PushEnvironment {
  const nav = navigator as Navigator & { standalone?: boolean };
  return {
    userAgent: nav.userAgent,
    platform: nav.platform ?? '',
    maxTouchPoints: nav.maxTouchPoints ?? 0,
    standalone: nav.standalone === true || window.matchMedia?.('(display-mode: standalone)').matches === true,
    hasServiceWorker: 'serviceWorker' in nav,
    hasPushManager: 'PushManager' in window,
    hasNotification: 'Notification' in window,
  };
}

export function isIos(env: PushEnvironment): boolean {
  // iPadOS reports itself as a Mac; touch gives it away
  return /iPad|iPhone|iPod/.test(env.userAgent) || (env.platform === 'MacIntel' && env.maxTouchPoints > 1);
}

export function pushSupport(env: PushEnvironment): PushSupport {
  if (isIos(env) && !env.standalone) return 'ios-needs-install';
  return env.hasServiceWorker && env.hasPushManager && env.hasNotification ? 'supported' : 'unsupported';
}

export function pushState(
  support: PushSupport,
  permission: NotificationPermission | null,
  subscribed: boolean,
): PushState {
  if (support !== 'supported') return support;
  if (permission === 'denied') return 'denied';
  return subscribed && permission === 'granted' ? 'on' : 'off';
}

export function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64 + '='.repeat((4 - (base64.length % 4)) % 4));
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function sameKey(subscription: PushSubscription, key: Uint8Array): boolean {
  const current = subscription.options?.applicationServerKey;
  if (!current) return true;
  const bytes = new Uint8Array(current);
  return bytes.length === key.length && bytes.every((value, index) => value === key[index]);
}

/** This browser's subscription, if any. Never waits for a service worker that is not there. */
export async function localSubscription(): Promise<PushSubscription | null> {
  const registration = await navigator.serviceWorker?.getRegistration();
  return (await registration?.pushManager.getSubscription()) ?? null;
}

export function registerSubscription(subscription: PushSubscription): Promise<PushDevice> {
  return apiFetch<PushDevice>('/v1/push/subscriptions', {
    method: 'POST',
    body: JSON.stringify(subscription.toJSON()),
  });
}

export class PermissionDeniedError extends Error {}

/** Ask for permission (call from a tap), subscribe and register this device with the server. */
export async function enablePush(publicKey: string): Promise<PushDevice> {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new PermissionDeniedError(permission);
  const registration = await navigator.serviceWorker.ready;
  const key = keyBytes(publicKey);
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, key)) {
    // The server has a new key (e.g. restored from another backup): subscribe again
    await subscription.unsubscribe();
    subscription = null;
  }
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  return registerSubscription(subscription);
}

/** Stop reminders on this device: remove it on the server, then in the browser. */
export async function disablePush(deviceId: number | null): Promise<void> {
  if (deviceId != null) {
    await apiFetch<void>(`/v1/push/subscriptions/${deviceId}`, { method: 'DELETE' });
  }
  await (await localSubscription())?.unsubscribe();
}

/** After logout: drop the browser's subscription (best effort; the server already removed it). */
export async function forgetLocalSubscription(): Promise<void> {
  try {
    await (await localSubscription())?.unsubscribe();
  } catch {
    // Nothing to do: without a subscription no reminder can arrive
  }
}
