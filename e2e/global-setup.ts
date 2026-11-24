import { chromium, expect, type FullConfig } from '@playwright/test';
import { mkdirSync } from 'node:fs';

/** Creates the first account through the setup page (or logs in) and stores the session. */
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL as string;
  const username = process.env.E2E_USERNAME ?? 'e2e';
  const password = process.env.E2E_PASSWORD ?? 'e2e-passwort-123';
  mkdirSync('.auth', { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL, locale: 'de-AT' });
  await page.goto('/');
  const setupHeading = page.getByRole('heading', { name: 'Einrichtung' });
  const loginHeading = page.getByRole('heading', { level: 1 });
  await expect(loginHeading).toBeVisible();

  if (await setupHeading.isVisible()) {
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
    await page.getByRole('button', { name: 'Anmelden' }).click();
  }
  await expect(page.getByRole('navigation', { name: 'Ansichten' })).toBeVisible();
  await page.context().storageState({ path: '.auth/state.json' });
  await browser.close();
}
