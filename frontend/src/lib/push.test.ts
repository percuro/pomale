import { describe, expect, it } from 'vitest';
import { isIos, keyBytes, pushState, pushSupport, type PushEnvironment } from './push';

const desktop: PushEnvironment = {
  userAgent: 'Mozilla/5.0 (X11; Linux x86_64) Chrome/140.0',
  platform: 'Linux x86_64',
  maxTouchPoints: 0,
  standalone: false,
  hasServiceWorker: true,
  hasPushManager: true,
  hasNotification: true,
};
const iphone: PushEnvironment = {
  ...desktop,
  userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1',
  platform: 'iPhone',
  maxTouchPoints: 5,
  hasPushManager: false,
  hasNotification: false,
};

describe('pushSupport', () => {
  it('desktop and Android browsers', () => {
    expect(pushSupport(desktop)).toBe('supported');
    expect(pushSupport({ ...desktop, hasPushManager: false })).toBe('unsupported');
    expect(pushSupport({ ...desktop, hasServiceWorker: false })).toBe('unsupported');
  });

  it('iPhone and iPad need the home-screen app', () => {
    expect(pushSupport(iphone)).toBe('ios-needs-install');
    expect(pushSupport({ ...iphone, standalone: true, hasPushManager: true, hasNotification: true })).toBe('supported');
    // Before iOS 16.4 even the installed app has no push
    expect(pushSupport({ ...iphone, standalone: true })).toBe('unsupported');
    const ipad = { ...desktop, userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari', platform: 'MacIntel', maxTouchPoints: 5 };
    expect(isIos(ipad)).toBe(true);
    expect(isIos({ ...ipad, maxTouchPoints: 0 })).toBe(false);
  });
});

describe('pushState', () => {
  it('combines support, permission and subscription', () => {
    expect(pushState('unsupported', null, false)).toBe('unsupported');
    expect(pushState('ios-needs-install', null, false)).toBe('ios-needs-install');
    expect(pushState('supported', 'denied', true)).toBe('denied');
    expect(pushState('supported', 'default', false)).toBe('off');
    expect(pushState('supported', 'granted', false)).toBe('off');
    expect(pushState('supported', 'granted', true)).toBe('on');
    // Permission withdrawn in the settings: the old subscription does not count
    expect(pushState('supported', 'default', true)).toBe('off');
  });
});

describe('keyBytes', () => {
  it('decodes base64url without padding', () => {
    expect([...keyBytes('AQID_-8')]).toEqual([1, 2, 3, 255, 239]);
    expect(keyBytes('B'.padEnd(87, 'A')).length).toBe(65);
  });
});
