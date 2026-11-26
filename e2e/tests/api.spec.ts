import { expect, test } from '@playwright/test';
import { createHabit, newAccount, today, uniqueName } from './helpers';

test('an API key reads what is open, cannot check off without permission, and stops after revoking', async ({
  page,
  request,
  playwright,
  baseURL,
}) => {
  const name = uniqueName('Lesen');
  const habit = await createHabit(request, name);
  await page.goto('/account');
  const section = page.locator('section', { has: page.getByRole('heading', { name: 'API-Schlüssel' }) });
  const label = uniqueName('Skript');
  await section.getByLabel('Name').fill(label);
  await section.getByRole('button', { name: 'Schlüssel anlegen' }).click();
  const key = (await section.locator('.copy-field', { hasText: 'Schlüssel' }).locator('code').first().textContent())!.trim();
  expect(key).toMatch(/^pm_/);
  await expect(section.locator('.copy-field', { hasText: 'Beispiel' }).locator('code')).toContainText('/api/v1/today');

  // A script: no cookie, no CSRF header (a new context would inherit both from the config)
  const script = await playwright.request.newContext({
    baseURL,
    storageState: { cookies: [], origins: [] },
    extraHTTPHeaders: { Authorization: `Bearer ${key}` },
  });
  const open = await script.get('/api/v1/today');
  expect(open.status()).toBe(200);
  const body = await open.json();
  expect(body.open.map((h: { name: string }) => h.name)).toContain(name);
  expect(body.message).toContain(name);
  const refused = await script.put(`/api/v1/habits/${habit.id}/days/${await today(request)}`, { data: { done: true } });
  expect(refused.status()).toBe(403);
  expect((await refused.json()).code).toBe('token.missing_scope');
  expect((await script.get('/api/v1/account/tokens')).status()).toBe(403);

  await section.getByRole('button', { name: 'Fertig' }).click();
  await section.getByRole('button', { name: `Schlüssel ${label} widerrufen` }).click();
  await expect(section.getByText(label)).toBeHidden();
  await expect.poll(async () => (await script.get('/api/v1/today')).status()).toBe(401);
  await script.dispose();
});

test('the API description is served as openapi.json only', async ({ request }) => {
  const schema = await request.get('/api/openapi.json');
  expect(schema.status()).toBe(200);
  expect((await schema.json()).servers).toEqual([{ url: '/api' }]);
  expect((await request.get('/api/docs')).status()).toBe(404);
});

test('a JSON export moves into an empty account', async ({ request, browser, baseURL }) => {
  const name = uniqueName('Umzug');
  const habit = await createHabit(request, name, { cue: 'nach dem Frühstück', color: 'teal' });
  expect((await request.put(`/api/v1/habits/${habit.id}/days/${await today(request)}`, { data: { done: true } })).ok()).toBeTruthy();
  const exported = await request.get('/api/v1/export.json');
  expect(exported.status()).toBe(200);
  const file = await exported.text();
  const habits = (JSON.parse(file) as { habits: unknown[] }).habits.length;

  const account = await newAccount(browser, request, baseURL!);
  const page = account.page;
  await page.goto('/account');
  const section = page.locator('section', { has: page.getByRole('heading', { name: 'Deine Daten' }) });
  await section.getByLabel('Export-Datei (.json)').setInputFiles({ name: 'pomale.json', mimeType: 'application/json', buffer: Buffer.from(file) });
  await expect(section.getByText(`Die Datei enthält ${habits} Gewohnheiten`)).toBeVisible();
  await section.getByRole('button', { name: 'Importieren' }).click();
  await expect(section.getByText(`Importiert: ${habits} Gewohnheiten`)).toBeVisible();
  // Not empty any more: no second import
  await page.reload();
  await expect(section.getByText(/nur in ein Konto ohne Gewohnheiten/)).toBeVisible();

  await page.goto('/today');
  await expect(page.locator('li.today-row', { hasText: name })).toContainText('nach dem Frühstück');
  await account.context.close();
});

test('an admin backs up now and sees it', async ({ page }) => {
  await page.goto('/admin');
  const section = page.locator('section', { has: page.getByRole('heading', { name: 'Backups' }) });
  await expect(section.getByText(/Täglich um 03:00/)).toBeVisible();
  await section.getByRole('button', { name: 'Jetzt sichern' }).click();
  await expect(section.getByText(/Backup pomale-\d{8}-\d{4}\.sql\.gz geschrieben/)).toBeVisible();
  await expect(section.getByText(/Letztes Backup:/)).toBeVisible();
});
