import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../docs/screenshots');

const SHOTS: Record<string, { page: string; heading: string; schemes: ('light' | 'dark')[]; scrollTo?: string }[]> = {
  desktop: [
    { page: '/today', heading: 'Today', schemes: ['light'] },
    { page: '/week', heading: 'Week', schemes: ['light', 'dark'] },
    { page: '/history', heading: 'History', schemes: ['light'] },
    { page: '/habits', heading: 'Habits', schemes: ['light'], scrollTo: 'Active' },
  ],
  phone: [
    { page: '/today', heading: 'Today', schemes: ['light', 'dark'] },
    { page: '/week', heading: 'Week', schemes: ['light'] },
  ],
};

async function signIn(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Open the demo' }).click();
  await expect(page.getByRole('navigation', { name: 'Views' })).toBeVisible();
  // The demo banner is not part of the product
  await page.addStyleTag({ content: '.demo-banner { display: none !important; }' });
}

test('screenshots', async ({ page }, testInfo) => {
  const device = testInfo.project.name;
  await signIn(page);
  for (const shot of SHOTS[device] ?? []) {
    for (const scheme of shot.schemes) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto(shot.page);
      await page.addStyleTag({ content: '.demo-banner { display: none !important; }' });
      await expect(page.getByRole('heading', { level: 1, name: shot.heading })).toBeVisible();
      await page.waitForLoadState('networkidle');
      if (shot.scrollTo) {
        await page.getByRole('heading', { name: shot.scrollTo, exact: true }).evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 90));
      }
      const name = `${shot.page.slice(1)}-${device}${scheme === 'dark' ? '-dark' : ''}.png`;
      await page.screenshot({ path: path.join(OUT, name) });
    }
  }
});
