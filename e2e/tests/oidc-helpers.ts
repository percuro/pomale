import { expect, type APIRequestContext, type Page } from '@playwright/test';

/** Set by CI (and local runs) when Dex runs next to the instance; see e2e/oidc/dex.yaml. */
export const OIDC = process.env.E2E_OIDC === '1';
/** Second instance with PASSWORD_LOGIN=off and OIDC_AUTO_CREATE=on */
export const OIDC_ONLY_URL = process.env.E2E_BASE_URL_2 ?? '';
const DEX_PASSWORD = 'password';

/** Sign in on Dex's login page; the browser then returns to pomale. */
export async function dexLogin(page: Page, email: string) {
  await page.locator('#login').fill(email);
  await page.locator('#password').fill(DEX_PASSWORD);
  await page.locator('#submit-login').click();
}

export function nav(page: Page) {
  return page.getByRole('navigation', { name: 'Ansichten' });
}

interface AdminUserRow {
  id: number;
  username: string;
  oidc_linked: boolean;
}

/**
 * Every project (chromium, webkit) runs the same tests against the same Dex users:
 * remove accounts that earlier runs linked, and the admin's own link.
 */
export async function forgetProviderAccounts(admin: APIRequestContext, adminPassword: string) {
  const me = (await (await admin.get('/api/v1/auth/me')).json()) as { id: number };
  const users = (await (await admin.get('/api/v1/admin/users')).json()) as AdminUserRow[];
  for (const user of users.filter((u) => u.oidc_linked || u.username.startsWith('sso'))) {
    if (user.id === me.id) {
      if (!user.oidc_linked) continue;
      const response = await admin.delete('/api/v1/account/oidc', { data: { password: adminPassword } });
      expect(response.status(), await response.text()).toBe(204);
    } else {
      const response = await admin.delete(`/api/v1/admin/users/${user.id}`);
      expect(response.status(), await response.text()).toBe(204);
    }
  }
}
