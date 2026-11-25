import { expect, test } from '@playwright/test';
import { createHabit, createLink, freshContext, newAccount, uniqueName } from './helpers';

test('admin invites, the new account accepts in its own browser and sees only its own habits', async ({
  page,
  request,
  browser,
  baseURL,
}) => {
  const adminHabit = uniqueName('Admin-Gewohnheit');
  await createHabit(request, adminHabit);

  await page.goto('/admin');
  await page.getByLabel('Notiz (optional)').fill('für Anna');
  await page.getByRole('button', { name: 'Link erstellen' }).click();
  const url = (await page.locator('.created-token code').textContent())!.trim();
  expect(url).toMatch(/\/invite#[\w-]{40,}$/);
  await page.getByRole('button', { name: 'Fertig, Link ausblenden' }).click();
  await expect(page.getByText('Einladung – für Anna')).toBeVisible();

  const anna = await freshContext(browser, baseURL!, { timezoneId: 'Europe/Berlin' });
  const annaPage = await anna.newPage();
  await annaPage.goto(url);
  await annaPage.getByLabel('Benutzername').fill(`anna${Date.now().toString(36)}`);
  await annaPage.getByLabel('Passwort (mindestens 12 Zeichen)').fill('annas-passwort-123');
  await annaPage.getByLabel('Passwort wiederholen').fill('annas-passwort-123');
  await annaPage.getByRole('button', { name: 'Konto anlegen' }).click();
  await expect(annaPage.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();

  const annaHabit = uniqueName('Annas Gewohnheit');
  await annaPage.goto('/habits');
  await annaPage.getByLabel('Name').fill(annaHabit);
  await annaPage.getByRole('button', { name: 'Anlegen' }).click();
  await expect(annaPage.locator('li.habit-item', { hasText: annaHabit })).toBeVisible();
  await expect(annaPage.getByText(adminHabit)).toHaveCount(0);

  await page.goto('/habits');
  await expect(page.locator('li.habit-item', { hasText: adminHabit })).toBeVisible();
  await expect(page.getByText(annaHabit)).toHaveCount(0);

  // The link works only once
  const again = await freshContext(browser, baseURL!);
  const againPage = await again.newPage();
  await againPage.goto(url);
  await expect(againPage.getByRole('alert')).toContainText('ungültig, abgelaufen oder schon benutzt');
  await Promise.all([anna.close(), again.close()]);
});

test('a password-reset link sets a new password and logs out the old sessions', async ({
  request,
  browser,
  baseURL,
}) => {
  const account = await newAccount(browser, request, baseURL!);
  await account.page.goto('/today');
  await expect(account.page.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();

  const url = await createLink(request, `/api/v1/admin/users/${account.id}/password-reset`);
  const fresh = await freshContext(browser, baseURL!);
  const freshPage = await fresh.newPage();
  await freshPage.goto(url);
  await expect(freshPage.getByRole('heading', { name: 'Zugang wiederherstellen' })).toBeVisible();
  await expect(freshPage.getByText(account.username)).toBeVisible();
  await freshPage.getByLabel('Passwort (mindestens 12 Zeichen)').fill('neues-passwort-456');
  await freshPage.getByLabel('Passwort wiederholen').fill('neues-passwort-456');
  await freshPage.getByRole('button', { name: 'Passwort speichern' }).click();
  await expect(freshPage.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();

  await account.page.reload();
  await expect(account.page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible();
  await Promise.all([account.context.close(), fresh.close()]);
});

test('a session on another device can be logged out from the account page', async ({ request, browser, baseURL }) => {
  const phone = await newAccount(browser, request, baseURL!);
  const laptop = await freshContext(browser, baseURL!);
  const laptopPage = await laptop.newPage();
  await laptopPage.goto('/');
  await laptopPage.getByLabel('Benutzername').fill(phone.username);
  await laptopPage.getByLabel('Passwort').fill(phone.password);
  await laptopPage.getByRole('button', { name: 'Anmelden', exact: true }).click();
  await expect(laptopPage.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();

  await phone.page.goto('/account');
  const other = phone.page.locator('.token-list li').filter({ hasNotText: 'dieses Gerät' });
  await expect(other).toHaveCount(1);
  await other.getByRole('button', { name: /abmelden/ }).click();
  await expect(other).toHaveCount(0);

  await laptopPage.reload();
  await expect(laptopPage.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible();
  await phone.page.reload();
  await expect(phone.page.getByRole('heading', { level: 1, name: 'Konto' })).toBeVisible();
  await Promise.all([phone.context.close(), laptop.close()]);
});

test('an English browser gets an English interface, and the account can switch to German', async ({
  request,
  browser,
  baseURL,
}) => {
  const account = await newAccount(browser, request, baseURL!, { locale: 'en-US' });
  const page = account.page;
  await page.goto('/today');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('heading', { level: 1, name: 'Today' })).toBeVisible();
  const header = page.locator('header');
  await expect(header).toContainText('Week');
  await expect(header).not.toContainText(/Heute|Woche|Gewohnheiten|Konto|Abmelden/);

  await page.goto('/account');
  await page.getByLabel('Language').selectOption('de');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Konto' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'de');
  await account.context.close();
});

test('changing the time zone moves "today", and the device time zone is offered', async ({
  request,
  browser,
  baseURL,
}) => {
  // The account uses the server default; the device is in New York
  const account = await newAccount(browser, request, baseURL!, { timezoneId: 'America/New_York' });
  const page = account.page;
  await page.goto('/today');
  const hint = page.getByRole('status').filter({ hasText: 'America/New_York' });
  const me = async () => (await (await account.context.request.get('/api/v1/auth/me')).json()) as Record<string, string>;
  if ((await me()).timezone !== 'America/New_York') {
    await hint.getByRole('button', { name: 'Auf America/New_York umstellen' }).click();
    await expect(hint).toBeHidden();
  }
  expect((await me()).timezone_setting).toBe('America/New_York');

  // Kiritimati (UTC+14) and Honolulu (UTC-10) are always on different calendar days
  const longDate = (timeZone: string) =>
    new Intl.DateTimeFormat('de-AT', { weekday: 'long', day: 'numeric', month: 'long', timeZone }).format(new Date());
  for (const zone of ['Pacific/Kiritimati', 'Pacific/Honolulu']) {
    await page.goto('/account');
    await page.getByLabel('Zeitzone').selectOption(zone);
    await page.getByRole('button', { name: 'Speichern' }).click();
    await expect(page.getByText('Gespeichert.')).toBeVisible();
    await page.goto('/today');
    await expect(page.locator('.page-head')).toContainText(longDate(zone));
  }
  await account.context.close();
});

test('logging out in the header returns to the login page', async ({ request, browser, baseURL }) => {
  const account = await newAccount(browser, request, baseURL!);
  const page = account.page;
  await page.goto('/account');
  await expect(page.getByRole('heading', { level: 1, name: 'Konto' })).toBeVisible();
  await page.getByRole('button', { name: 'Abmelden', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Anmelden', exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Ansichten' })).toHaveCount(0);
  await account.context.close();
});
