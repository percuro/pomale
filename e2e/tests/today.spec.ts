import { expect, test } from '@playwright/test';
import { createHabit, dayState, today, todayRow, uniqueName } from './helpers';

test('check off and undo today without the row moving', async ({ page, request }) => {
  const name = uniqueName('Lesen');
  const habit = await createHabit(request, name, { cue: 'nach dem Frühstück' });
  await page.goto('/today');
  const row = todayRow(page, name);
  const main = row.getByRole('button', { name: new RegExp(name) }).first();
  await expect(main).toHaveAttribute('aria-pressed', 'false');
  // Position in the document (not the viewport: clicking may scroll)
  const top = () => row.evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  await row.scrollIntoViewIfNeeded();
  const before = await top();

  await main.click();
  await expect(main).toHaveAttribute('aria-pressed', 'true');
  await expect(row).toContainText('Erledigt');
  const undo = row.getByRole('button', { name: `${name}: Rückgängig` });
  await expect(undo).toBeVisible();
  expect(await top()).toBe(before);
  await expect.poll(async () => (await dayState(request, habit.id, await today(request))).done).toBe(true);

  await undo.click();
  await expect(main).toHaveAttribute('aria-pressed', 'false');
  await expect(row).toContainText('Offen');
  await expect.poll(async () => (await dayState(request, habit.id, await today(request))).done).toBe(false);
});
