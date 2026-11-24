import { expect, test } from '@playwright/test';
import { createHabit, today, uniqueName } from './helpers';

test('week grid works with the keyboard and updates the quota', async ({ page, request }) => {
  const name = uniqueName('Laufen');
  const day = await today(request);
  await createHabit(request, name, { start_on: day });
  await page.goto('/week');
  const row = page.getByRole('row').filter({ hasText: name });
  const cell = row.locator('[role=gridcell].is-today button');
  await cell.focus();
  await page.keyboard.press('Space');
  await expect(cell).toHaveAttribute('aria-pressed', 'true');
  await expect(row).toContainText('1 von 1');
  await page.keyboard.press('Enter');
  await expect(cell).toHaveAttribute('aria-pressed', 'false');
  await expect(row).toContainText('nichts fällig');

  // Arrow keys move focus within the row
  await page.keyboard.press('Home');
  const first = row.locator('[role=gridcell] button').first();
  await expect(first).toBeFocused();
});
