import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { SETUP_CHECK } from '../global-setup';
import { axeViolations, createHabit, createLink, freshContext, newAccount, sidewaysOverflow, todayRow, uniqueName } from './helpers';

// The page scans in design.spec.ts see each page as it loads. These see what only appears after
// a click (dialogs, forms, results), the pages without an account, and the English interface.

async function heading(page: Page) {
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.waitForLoadState('networkidle');
}

test('the setup page of a fresh instance has no violations and fits 320 px', async () => {
  test.skip(!existsSync(SETUP_CHECK), 'the instance was set up before this run');
  const { violations, overflow } = JSON.parse(readFileSync(SETUP_CHECK, 'utf8')) as { violations: string[]; overflow: number };
  expect(violations).toEqual([]);
  expect(overflow).toBeLessThanOrEqual(0);
});

for (const scheme of ['light', 'dark'] as const) {
  test(`pages without an account have no violations and fit 320 px (${scheme})`, async ({ browser, baseURL, request }) => {
    const link = new URL(await createLink(request));
    const context = await freshContext(browser, baseURL!);
    const page = await context.newPage();
    await page.emulateMedia({ colorScheme: scheme });
    const found: string[] = [];
    const pages = {
      login: '/',
      invitation: `${link.pathname}${link.hash}`,
      // Without a token: the same error state as a used link, without counting as a failed attempt
      'invitation without a token': '/invite',
      registration: '/register',
    };
    for (const [label, path] of Object.entries(pages)) {
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.goto(path);
      await heading(page);
      found.push(...(await axeViolations(page, label)));
      await page.setViewportSize({ width: 320, height: 640 });
      expect(await sidewaysOverflow(page), label).toBeLessThanOrEqual(0);
    }
    await context.close();
    expect(found).toEqual([]);
  });

  test(`dialogs, forms and results have no violations (${scheme})`, async ({ page, context, request, browser, baseURL }) => {
    await page.emulateMedia({ colorScheme: scheme });
    const plain = uniqueName('Lesen');
    const water = uniqueName('Wasser');
    const group = uniqueName('Abends');
    await createHabit(request, plain);
    await createHabit(request, water, { goal_type: 'quantity', target: 8, unit: 'Gläser' });
    const old = await createHabit(request, uniqueName('Alt'));
    expect((await request.post(`/api/v1/habits/${old.id}/archive`)).ok()).toBeTruthy();
    expect((await request.post('/api/v1/groups', { data: { name: group } })).ok()).toBeTruthy();
    const found: string[] = [];
    const scan = async (label: string) => found.push(...(await axeViolations(page, label)));

    await page.goto('/today');
    await heading(page);
    await todayRow(page, plain).getByRole('button', { name: `${plain}: Notiz` }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await scan('note dialog');
    await page.keyboard.press('Escape');

    await context.setOffline(true);
    await todayRow(page, plain).getByRole('button', { name: new RegExp(plain) }).first().click();
    await expect(page.getByRole('status').filter({ hasText: 'Offline' })).toBeVisible();
    await scan('offline and waiting');
    await context.setOffline(false);
    await expect(todayRow(page, plain)).not.toContainText('wartet auf Übertragung');

    await page.goto('/week');
    await heading(page);
    await page.getByRole('button', { name: new RegExp(`^${water}, .*: 0 von 8`) }).first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await scan('amount dialog');
    await page.keyboard.press('Escape');

    await page.goto('/habits');
    await heading(page);
    const item = page.locator('li.habit-item', { hasText: plain });
    await item.getByRole('button', { name: 'Kurzbefehl', exact: true }).click();
    await item.getByRole('button', { name: 'Schlüssel anlegen' }).click();
    await expect(item.getByRole('status').filter({ hasText: 'Bearer' })).toBeVisible();
    await scan('shortcut key');
    await item.getByRole('button', { name: 'Bearbeiten' }).click();
    await expect(page.getByRole('button', { name: 'Speichern' })).toBeVisible();
    await scan('editing a habit');
    await page.getByRole('button', { name: 'Abbrechen' }).first().click();
    await page.locator('details.archived > summary').click();
    await scan('archived habits');
    await page.getByRole('button', { name: `Gruppe ${group} löschen` }).click();
    await expect(page.getByRole('alertdialog')).toBeVisible();
    await scan('confirmation');
    await page.getByRole('alertdialog').getByRole('button', { name: 'Abbrechen' }).click();

    await page.goto('/account');
    await heading(page);
    const keys = page.locator('section', { has: page.getByRole('heading', { name: 'API-Schlüssel' }) });
    await keys.getByLabel('Name').fill(uniqueName('Skript'));
    await keys.getByRole('button', { name: 'Schlüssel anlegen' }).click();
    await expect(keys.getByRole('status').filter({ hasText: 'angelegt' })).toBeVisible();
    await scan('new API key');
    await page.goto('/admin');
    await heading(page);
    await page.getByRole('button', { name: 'Link erstellen' }).click();
    await expect(page.getByRole('button', { name: 'Fertig, Link ausblenden' })).toBeVisible();
    await scan('invitation link');
    const backups = page.locator('section', { has: page.getByRole('heading', { name: 'Backups' }) });
    await backups.getByRole('button', { name: 'Jetzt sichern' }).click();
    await expect(backups.getByRole('status').first()).toBeVisible();
    await scan('backup result');

    // Importing is offered only to an account without habits: a new one, with this account's export
    const file = await (await request.get('/api/v1/export.json')).text();
    const account = await newAccount(browser, request, baseURL!);
    await account.page.emulateMedia({ colorScheme: scheme });
    await account.page.goto('/account');
    await heading(account.page);
    const data = account.page.locator('section', { has: account.page.getByRole('heading', { name: 'Deine Daten' }) });
    await data.getByLabel('Export-Datei (.json)').setInputFiles({ name: 'pomale.json', mimeType: 'application/json', buffer: Buffer.from(file) });
    await expect(data.getByText(/Die Datei enthält/)).toBeVisible();
    found.push(...(await axeViolations(account.page, 'import preview')));
    await account.context.close();

    expect(found).toEqual([]);
  });
}

test('the English interface has no violations', async ({ browser, baseURL, request }) => {
  // The admin's account has German set; a new account follows the browser's language
  const account = await newAccount(browser, request, baseURL!, { locale: 'en-US' });
  const page = account.page;
  await createHabit(account.context.request, uniqueName('Read'));
  const found: string[] = [];
  for (const path of ['/', '/today', '/week', '/history', '/habits', '/account']) {
    await page.goto(path);
    await heading(page);
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    found.push(...(await axeViolations(page, path)));
  }
  await account.context.close();
  expect(found).toEqual([]);
});

test('after a change of page the focus is at the start of the content', async ({ page }) => {
  await page.goto('/today');
  await heading(page);
  await page.getByRole('navigation', { name: 'Ansichten' }).getByRole('link', { name: 'Woche' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Woche' })).toBeVisible();
  await expect(page.locator('main#content')).toBeFocused();
  await expect(page.locator('#page-announcer')).toHaveText('Woche');
  // The next Tab goes into the page, not back to the navigation
  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.getElementById('content')!.contains(document.activeElement))).toBe(true);
});
