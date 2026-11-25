import { expect, test, type Browser } from '@playwright/test';
import { createLink, freshContext } from './helpers';
import { dexLogin, forgetProviderAccounts, nav, OIDC } from './oidc-helpers';

const ADMIN_PASSWORD = process.env.E2E_PASSWORD ?? 'e2e-passwort-123';

test.describe('sign-in through OIDC (Dex)', () => {
  test.skip(!OIDC, 'needs Dex: set E2E_OIDC=1');

  test.beforeEach(async ({ request }) => {
    await forgetProviderAccounts(request, ADMIN_PASSWORD);
  });

  /** Accept an invitation with the provider instead of a password */
  async function signUpWithDex(browser: Browser, request: Parameters<typeof createLink>[0], baseURL: string, email: string) {
    const url = await createLink(request);
    const context = await freshContext(browser, baseURL);
    const page = await context.newPage();
    const username = `sso${Date.now().toString(36)}`;
    await page.goto(url);
    await page.getByLabel('Benutzername').fill(username);
    await page.getByRole('button', { name: 'Weiter mit Dex' }).click();
    await dexLogin(page, email);
    await expect(nav(page)).toBeVisible();
    return { context, page, username };
  }

  test('an invited person signs up and logs in again with the provider', async ({ browser, request, baseURL }) => {
    const { context, page, username } = await signUpWithDex(browser, request, baseURL!, 'anna@example.org');
    await page.goto('/account');
    await expect(page.getByText(`Angemeldet als ${username}`)).toBeVisible();
    await expect(page.getByText('Mit Dex verknüpft als anna@example.org')).toBeVisible();
    // No password yet: the account can set one, without a current password
    await expect(page.getByRole('button', { name: 'Passwort festlegen' })).toBeVisible();
    await expect(page.getByLabel('Aktuelles Passwort')).toHaveCount(0);

    await page.getByRole('button', { name: 'Abmelden', exact: true }).click();
    await page.getByRole('button', { name: 'Anmelden mit Dex' }).click();
    await dexLogin(page, 'anna@example.org');
    await expect(nav(page)).toBeVisible();
    await context.close();
  });

  test('the admin links and unlinks their account and sees it in the log', async ({ page }) => {
    await page.goto('/account');
    await page.getByRole('button', { name: 'Mit Dex verknüpfen' }).click();
    const dialog = page.getByRole('alertdialog');
    await dialog.getByLabel('Passwort zur Bestätigung').fill(ADMIN_PASSWORD);
    await dialog.getByRole('button', { name: 'Mit Dex verknüpfen' }).click();
    await dexLogin(page, 'ben@example.org');
    await expect(page.getByRole('status').filter({ hasText: 'Mit Dex verknüpft.' })).toBeVisible();
    await expect(page.getByText('Mit Dex verknüpft als ben@example.org')).toBeVisible();

    await page.getByRole('button', { name: 'Verknüpfung lösen' }).click();
    await dialog.getByLabel('Passwort zur Bestätigung').fill(ADMIN_PASSWORD);
    await dialog.getByRole('button', { name: 'Verknüpfung lösen' }).click();
    await expect(page.getByText('Nicht mit Dex verknüpft.')).toBeVisible();

    await page.goto('/admin');
    const log = page.locator('.audit-list');
    await expect(log.getByText('mit dem Anbieter verknüpft').first()).toBeVisible();
    await expect(log.getByText(/Anbieter-Verknüpfung von \S+ entfernt von/).first()).toBeVisible();
  });

  test('a deactivated account cannot log in with the provider', async ({ browser, request, baseURL }) => {
    const { context, username } = await signUpWithDex(browser, request, baseURL!, 'anna@example.org');
    await context.close();
    const users = (await (await request.get('/api/v1/admin/users')).json()) as { id: number; username: string }[];
    const id = users.find((user) => user.username === username)!.id;
    expect((await request.patch(`/api/v1/admin/users/${id}`, { data: { is_active: false } })).ok()).toBeTruthy();

    const fresh = await freshContext(browser, baseURL!);
    const page = await fresh.newPage();
    await page.goto('/');
    await page.getByRole('button', { name: 'Anmelden mit Dex' }).click();
    await dexLogin(page, 'anna@example.org');
    await expect(page.getByRole('alert')).toContainText('ist deaktiviert');
    await fresh.close();
  });

  test('unknown provider accounts and cancelled sign-ins show an error', async ({ browser, baseURL }) => {
    const fresh = await freshContext(browser, baseURL!);
    const page = await fresh.newPage();
    await page.goto('/');
    await page.getByRole('button', { name: 'Anmelden mit Dex' }).click();
    await dexLogin(page, 'carla@example.org');
    await expect(page.getByRole('alert')).toContainText('gibt es hier kein Konto');
    // The error is shown once and removed from the address bar
    expect(new URL(page.url()).hash).toBe('');

    // The provider reports that the person cancelled. Start through the API of the same browser
    // context (shares the cookies; a page.route would miss requests the service worker answers).
    const started = await page.request.post('/api/v1/auth/oidc/start', {
      data: { purpose: 'login' },
      headers: { 'X-Habit-CSRF': '1', Origin: baseURL! },
    });
    expect(started.ok(), await started.text()).toBeTruthy();
    const { authorize_url } = (await started.json()) as { authorize_url: string };
    const state = new URL(authorize_url).searchParams.get('state')!;
    await page.goto(`/api/v1/auth/oidc/callback?error=access_denied&state=${encodeURIComponent(state)}`);
    await expect(page.getByRole('alert')).toContainText('beim Anbieter abgebrochen');
    await fresh.close();
  });
});
