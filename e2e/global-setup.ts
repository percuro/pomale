import { chromium, expect, type FullConfig } from '@playwright/test';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { axeViolations, sidewaysOverflow } from './tests/helpers';

/** The setup page exists only before the first account: checked here, reported by accessibility.spec. */
export const SETUP_CHECK = '.auth/setup-check.json';

/** Creates the first account through the setup page (or logs in) and stores the session. */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL as string;
  const username = process.env.E2E_USERNAME ?? 'e2e';
  const password = process.env.E2E_PASSWORD ?? 'e2e-passwort-123';
  mkdirSync('.auth', { recursive: true });
  rmSync(SETUP_CHECK, { force: true });

  const browser = await chromium.launch();
  // An explicit context: axe cannot scan a page of the default one
  const page = await (await browser.newContext({ baseURL, locale: 'de-AT' })).newPage();
  await page.goto('/');
  const setupHeading = page.getByRole('heading', { name: 'Einrichtung' });
  const loginHeading = page.getByRole('heading', { level: 1 });
  await expect(loginHeading).toBeVisible();

  if (await setupHeading.isVisible()) {
    const violations = [];
    for (const scheme of ['light', 'dark'] as const) {
      // Loaded again in the scheme: right after a switch, colours are still in their transition
      await page.emulateMedia({ colorScheme: scheme });
      await page.reload();
      await expect(setupHeading).toBeVisible();
      violations.push(...(await axeViolations(page, `setup (${scheme})`)));
    }
    await page.setViewportSize({ width: 320, height: 640 });
    const overflow = await sidewaysOverflow(page);
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.emulateMedia({ colorScheme: 'light' });
    writeFileSync(SETUP_CHECK, JSON.stringify({ violations, overflow }));
    const token = process.env.E2E_SETUP_TOKEN;
    if (!token) throw new Error('Fresh instance: set E2E_SETUP_TOKEN from the server log');
    await page.getByLabel('Setup-Token').fill(token);
    await page.getByLabel('Benutzername').fill(username);
    await page.getByLabel('Passwort (mindestens 12 Zeichen)').fill(password);
    await page.getByLabel('Passwort wiederholen').fill(password);
    await page.getByRole('button', { name: 'Zugang anlegen' }).click();
  } else {
    await page.getByLabel('Benutzername').fill(username);
    await page.getByLabel('Passwort').fill(password);
    await page.getByRole('button', { name: 'Anmelden', exact: true }).click();
  }
  await expect(page.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();
  await page.context().storageState({ path: '.auth/state.json' });
  await browser.close();
}
