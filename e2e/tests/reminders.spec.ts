import { createECDH } from 'node:crypto';
import { expect, test, type Page } from '@playwright/test';
import { createHabit, uniqueName } from './helpers';

/**
 * Real push delivery needs a push service (FCM, Apple, Mozilla) that CI cannot reach; the backend
 * tests cover sending against a mocked one. Here PushManager is stubbed: it hands out
 * subscriptions on push.invalid, which the instance allows with PUSH_ALLOWED_HOSTS=push.invalid
 * (the .invalid domain never resolves, so a test notification fails visibly).
 */
async function stubPushManager(page: Page, answer: NotificationPermission = 'granted') {
  const p256dh = createECDH('prime256v1').generateKeys().toString('base64url');
  await page.addInitScript(({ key, answer }) => {
    if (typeof PushManager === 'undefined') return;
    // Headless Chromium reports notifications as blocked whatever was granted
    let permission: NotificationPermission = 'default';
    Object.defineProperty(Notification, 'permission', { get: () => permission });
    Notification.requestPermission = async () => {
      permission = answer;
      return permission;
    };
    let current: PushSubscription | null = null;
    const fake = (endpoint: string) =>
      ({
        endpoint,
        options: { applicationServerKey: null, userVisibleOnly: true },
        toJSON: () => ({ endpoint, keys: { p256dh: key, auth: 'MDEyMzQ1Njc4OWFiY2RlZg' } }),
        unsubscribe: async () => {
          current = null;
          return true;
        },
      }) as unknown as PushSubscription;
    PushManager.prototype.subscribe = async () => {
      current = fake(`https://push.invalid/e2e/${Date.now()}`);
      return current;
    };
    PushManager.prototype.getSubscription = async () => current;
  }, { key: p256dh, answer });
}

test('reminder times on a habit', async ({ page, request }) => {
  const name = uniqueName('Erinnern');
  await page.goto('/habits');
  const form = page.getByRole('form', { name: 'Neue Gewohnheit' });
  await form.getByLabel('Name').fill(name);
  await form.getByRole('button', { name: 'Uhrzeit hinzufügen' }).click();
  await form.getByLabel('Erinnerungszeit 1', { exact: true }).fill('20:00');
  await form.getByRole('button', { name: 'Uhrzeit hinzufügen' }).click();
  await form.getByLabel('Erinnerungszeit 2', { exact: true }).fill('07:30');
  await form.getByRole('button', { name: 'Anlegen' }).click();

  const item = page.locator('li.habit-item', { hasText: name });
  await expect(item).toContainText('Erinnerung 07:30, 20:00');

  await item.getByRole('button', { name: 'Bearbeiten' }).click();
  const edit = page.getByRole('form', { name: new RegExp(name) });
  await edit.getByRole('button', { name: 'Erinnerungszeit 1 entfernen' }).click();
  await edit.getByLabel('Erinnerungszeit 1', { exact: true }).fill('21:15');
  await edit.getByRole('button', { name: 'Speichern' }).click();
  await expect(item).toContainText('Erinnerung 21:15');

  await page.reload();
  await expect(page.locator('li.habit-item', { hasText: name })).toContainText('Erinnerung 21:15');
  const habits = (await (await request.get('/api/v1/habits')).json()) as { name: string; reminders: string[] }[];
  expect(habits.find((h) => h.name === name)?.reminders).toEqual(['21:15']);
});

test('the same time twice is refused in the form', async ({ page }) => {
  await page.goto('/habits');
  const form = page.getByRole('form', { name: 'Neue Gewohnheit' });
  await form.getByLabel('Name').fill(uniqueName('Doppelt'));
  for (const n of [1, 2]) {
    await form.getByRole('button', { name: 'Uhrzeit hinzufügen' }).click();
    await form.getByLabel(`Erinnerungszeit ${n}`, { exact: true }).fill('08:00');
  }
  await expect(form.getByRole('alert')).toContainText('Jede Uhrzeit nur einmal');
  await expect(form.getByRole('button', { name: 'Anlegen' })).toBeDisabled();
});

test('turn reminders on and off for this device', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'needs the Push API (desktop Chrome)');
  await stubPushManager(page);
  await page.goto('/account');
  const section = page.getByRole('region', { name: 'Erinnerungen' });
  await expect(section).toContainText('Erinnerungen sind aus.');

  await section.getByRole('button', { name: 'Auf diesem Gerät einschalten' }).click();
  await expect(section).toContainText('Erinnerungen sind an.');
  const mine = section.locator('li', { hasText: 'dieses Gerät' });
  await expect(mine).toHaveCount(1);

  // push.invalid does not exist: the server reports that the push service did not take it
  await section.getByRole('button', { name: 'Test senden' }).click();
  await expect(section.getByRole('alert')).toContainText('Push-Dienst');
  await expect(mine).toContainText('letzter Versuch fehlgeschlagen');

  await section.getByRole('button', { name: 'Auf diesem Gerät ausschalten' }).click();
  await expect(section).toContainText('Erinnerungen sind aus.');
  await expect(section.locator('li', { hasText: 'dieses Gerät' })).toHaveCount(0);
});

test('permission refused keeps reminders off', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium', 'needs the Push API (desktop Chrome)');
  await stubPushManager(page, 'denied');
  await page.goto('/account');
  const section = page.getByRole('region', { name: 'Erinnerungen' });
  await section.getByRole('button', { name: 'Auf diesem Gerät einschalten' }).click();
  await expect(section.getByRole('alert')).toContainText('nicht erlaubt');
  await expect(section).toContainText('Benachrichtigungen sind blockiert.');
});

test('iPhone in Safari is told to use the home-screen app', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'iphone-webkit', 'iPhone only');
  await page.goto('/account');
  const section = page.getByRole('region', { name: 'Erinnerungen' });
  await expect(section).toContainText('nur in der App auf dem Home-Bildschirm');
  await expect(section).toContainText('Zum Home-Bildschirm');
  await expect(section.getByRole('button', { name: 'Auf diesem Gerät einschalten' })).toHaveCount(0);
});

test('reminder hint links to the account when no device is set up', async ({ page, request }) => {
  const devices = (await (await request.get('/api/v1/push/subscriptions')).json()) as unknown[];
  test.skip(devices.length > 0, 'the shared account has a device from another run');
  const name = uniqueName('Hinweis');
  await createHabit(request, name, { reminders: ['09:00'] });
  await page.goto('/habits');
  await page.locator('li.habit-item', { hasText: name }).getByRole('button', { name: 'Bearbeiten' }).click();
  const edit = page.getByRole('form', { name: new RegExp(name) });
  await expect(edit).toContainText('Noch bekommt kein Gerät Erinnerungen.');
  await expect(edit.getByRole('link', { name: 'Im Konto einschalten' })).toHaveAttribute('href', /\/account/);
});
