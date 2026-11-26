import { expect, test, type Page } from '@playwright/test';
import { axeViolations, createHabit, freshContext, setDay, sidewaysOverflow, today, uniqueName } from './helpers';

const PAGES = ['/today', '/week', '/history', '/habits', '/account', '/admin'];

/** Habits of every goal type, with a day that is done, so that all states of the ring appear. */
async function someHabits(page: Page) {
  const request = page.request;
  const day = await today(request);
  const plain = await createHabit(request, uniqueName('Lesen'), { color: 'amber', cue: 'nach dem Abendessen' });
  await setDay(request, plain.id, day, true);
  const amount = await createHabit(request, uniqueName('Wasser'), { goal_type: 'quantity', target: 8, unit: 'Gläser', color: 'teal' });
  expect((await request.put(`/api/v1/habits/${amount.id}/days/${day}`, { data: { value: 5 } })).ok()).toBeTruthy();
  await createHabit(request, uniqueName('Laufen'), { goal_type: 'weekly_count', target: 3, color: 'red' });
}

async function open(page: Page, path: string) {
  await page.goto(path);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.waitForLoadState('networkidle');
}

for (const scheme of ['light', 'dark'] as const) {
  test(`no accessibility violations in the ${scheme} scheme (WCAG 2.2 AA)`, async ({ page, browser, baseURL }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await someHabits(page);
    const found: string[] = [];
    const scan = async (target: Page, path: string) => {
      await open(target, path);
      found.push(...(await axeViolations(target, path)));
    };
    for (const path of PAGES) await scan(page, path);

    const anonymous = await freshContext(browser, baseURL!);
    const login = await anonymous.newPage();
    await login.emulateMedia({ colorScheme: scheme });
    await scan(login, '/');
    await anonymous.close();
    expect(found).toEqual([]);
  });
}

test('every page fits a window 320 px wide without scrolling sideways', async ({ page }) => {
  await someHabits(page);
  await page.setViewportSize({ width: 320, height: 640 });
  for (const path of PAGES) {
    await open(page, path);
    expect(await sidewaysOverflow(page), path).toBeLessThanOrEqual(0);
  }
});

test('the window title follows the page, the navigation follows the width', async ({ page }) => {
  await open(page, '/week');
  await expect(page).toHaveTitle('Woche · pomale');

  const navigation = page.getByRole('navigation', { name: 'Ansichten' });
  const position = () => navigation.evaluate((element) => getComputedStyle(element).position);
  // Phone and tablet: at the bottom, within reach of the thumb; wide window: in the top bar
  await page.setViewportSize({ width: 390, height: 800 });
  await open(page, '/today');
  expect(await position()).toBe('fixed');
  await expect(navigation.getByRole('link', { name: 'Heute' })).toHaveAttribute('aria-current', 'page');
  await page.setViewportSize({ width: 1000, height: 800 });
  expect(await position()).toBe('static');
});

test('the account page has the way out and, for an administrator, the administration', async ({ page }) => {
  await open(page, '/today');
  await page.getByRole('link', { name: 'Konto' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Konto' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Abmelden', exact: true })).toBeVisible();
  await page.getByRole('link', { name: 'Verwaltung' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Verwaltung' })).toBeVisible();
});
