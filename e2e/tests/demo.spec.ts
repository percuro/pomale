import { expect, test } from '@playwright/test';

// Third instance with DEMO_MODE=true: sample data, reset every full hour
const DEMO_URL = process.env.E2E_BASE_URL_3 ?? '';

test.use({
  baseURL: DEMO_URL || undefined,
  storageState: { cookies: [], origins: [] },
  extraHTTPHeaders: { 'X-Habit-CSRF': '1', Origin: DEMO_URL },
});

test.describe('demo instance', () => {
  test.skip(!DEMO_URL, 'needs an instance with DEMO_MODE=true: set E2E_BASE_URL_3');

  test('one click opens the demo, sample data can be checked off, shared things are locked', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Das ist eine Demo mit Beispieldaten.')).toBeVisible();
    await page.getByRole('button', { name: 'Demo öffnen' }).click();

    await expect(page.getByText('Demo: Probier alles aus')).toBeVisible();
    await page.goto('/today');
    await expect(page.getByRole('heading', { level: 1, name: 'Heute' })).toBeVisible();
    // Water is due every day (3 of 8 glasses after a reset; earlier runs within the hour may have added some)
    const more = page.getByRole('button', { name: 'Water: eins mehr' });
    const value = more.locator('xpath=..').locator('.stepper-value');
    const before = Number(await value.textContent());
    expect(before).toBeGreaterThanOrEqual(3);
    await more.click();
    await expect(value).toHaveText(String(before + 1));

    await page.goto('/account');
    await expect(page.getByRole('heading', { level: 2, name: 'Deine Daten' })).toBeVisible();
    for (const name of ['Passwort', 'Geräte', 'API-Schlüssel', 'Konto löschen', 'Importieren']) {
      await expect(page.getByRole('heading', { name, exact: true })).toHaveCount(0);
    }
    await page.goto('/habits');
    await expect(page.getByText('Water').first()).toBeVisible();
    await expect(page.getByRole('button', { name: 'Kurzbefehl' })).toHaveCount(0);

    // The API refuses what the interface hides
    const response = await page.request.post('/api/v1/account/tokens', { data: { label: 'x', scopes: ['read'] } });
    expect(response.status()).toBe(403);
    expect((await response.json()).code).toBe('demo.not_allowed');
  });
});
