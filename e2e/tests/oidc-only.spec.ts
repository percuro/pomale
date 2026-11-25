import { expect, test } from '@playwright/test';
import { dexLogin, nav, OIDC, OIDC_ONLY_URL } from './oidc-helpers';

// Second instance: PASSWORD_LOGIN=off, OIDC_AUTO_CREATE=on, set up through the provider
test.use({
  baseURL: OIDC_ONLY_URL || undefined,
  storageState: { cookies: [], origins: [] },
  extraHTTPHeaders: { 'X-Habit-CSRF': '1', Origin: OIDC_ONLY_URL },
});

test.describe('instance without passwords', () => {
  test.skip(!OIDC || !OIDC_ONLY_URL, 'needs Dex and a second instance: set E2E_OIDC=1 and E2E_BASE_URL_2');

  test('setup, admin sign-in and automatic accounts work through the provider only', async ({ page, browser }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    if (await page.getByRole('heading', { name: 'Einrichtung' }).isVisible()) {
      const token = process.env.E2E_SETUP_TOKEN_2;
      if (!token) throw new Error('Fresh second instance: set E2E_SETUP_TOKEN_2 from its log');
      await page.getByLabel('Setup-Token').fill(token);
      await page.getByLabel('Benutzername').fill('chefin');
      await expect(page.getByLabel('Passwort (mindestens 12 Zeichen)')).toHaveCount(0);
      await page.getByRole('button', { name: 'Weiter mit Dex' }).click();
    } else {
      await expect(page.getByLabel('Passwort')).toHaveCount(0);
      await page.getByRole('button', { name: 'Anmelden mit Dex' }).click();
    }
    await dexLogin(page, 'anna@example.org');
    await expect(nav(page)).toBeVisible();
    await page.goto('/admin');
    await expect(page.getByRole('heading', { level: 1, name: 'Verwaltung' })).toBeVisible();

    // Ben has no account yet: it is created at the first sign-in
    const context = await browser.newContext({ baseURL: OIDC_ONLY_URL, storageState: { cookies: [], origins: [] }, locale: 'de-AT' });
    const ben = await context.newPage();
    await ben.goto('/');
    await expect(ben.getByLabel('Passwort')).toHaveCount(0);
    await ben.getByRole('button', { name: 'Anmelden mit Dex' }).click();
    await dexLogin(ben, 'ben@example.org');
    await expect(nav(ben)).toBeVisible();
    await ben.goto('/account');
    await expect(ben.getByText('Angemeldet als ben (Benutzer')).toBeVisible();
    // Passwords are off: no password section, the link cannot be removed
    await expect(ben.getByRole('heading', { name: 'Passwort' })).toHaveCount(0);
    await expect(ben.getByRole('button', { name: 'Verknüpfung lösen' })).toHaveCount(0);
    await context.close();
  });
});
