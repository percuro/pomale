import { expect, test } from '@playwright/test';
import { createHabit, dayState, setDay, today, todayRow, uniqueName } from './helpers';

test('check-in while offline is queued, marked and sent when back online', async ({ page, context, request }) => {
  const name = uniqueName('Offline');
  const habit = await createHabit(request, name);
  await page.goto('/today');
  await expect(todayRow(page, name)).toBeVisible();

  await context.setOffline(true);
  await todayRow(page, name).getByRole('button', { name: new RegExp(name) }).first().click();
  await expect(todayRow(page, name)).toContainText('wartet auf Übertragung');
  await expect(page.getByRole('status').filter({ hasText: 'Offline' })).toBeVisible();
  expect((await dayState(request, habit.id, await today(request))).done).toBe(false);

  await context.setOffline(false);
  await expect(todayRow(page, name)).not.toContainText('wartet auf Übertragung');
  await expect.poll(async () => (await dayState(request, habit.id, await today(request))).done).toBe(true);
});

test('a conflicting change from another device asks instead of overwriting', async ({ page, context, request }) => {
  const name = uniqueName('Konflikt');
  const habit = await createHabit(request, name);
  const day = await today(request);
  await page.goto('/today');
  await expect(todayRow(page, name)).toBeVisible();

  await context.setOffline(true);
  await todayRow(page, name).getByRole('button', { name: new RegExp(name) }).first().click();
  // Meanwhile on another device: done, then undone (server version 2, state open)
  await setDay(request, habit.id, day, true);
  await setDay(request, habit.id, day, false);
  await context.setOffline(false);

  const dialog = page.getByRole('alertdialog', { name: 'Abweichende Änderung' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(name);
  expect((await dayState(request, habit.id, day)).done).toBe(false);
  await dialog.getByRole('button', { name: 'Gerätestand übernehmen' }).click();
  await expect(dialog).toBeHidden();
  await expect.poll(async () => (await dayState(request, habit.id, day)).done).toBe(true);
});
