import { expect, test } from '@playwright/test';
import { createHabit, uniqueName } from './helpers';

test('shortcut key checks off today and stops working after revoking', async ({ page, request, playwright, baseURL }) => {
  const name = uniqueName('Wasser');
  const habit = await createHabit(request, name);
  await page.goto('/habits');
  const item = page.locator('li.habit-item', { hasText: name });
  await item.getByRole('button', { name: 'Kurzbefehl', exact: true }).click();
  await item.getByRole('button', { name: 'Schlüssel anlegen' }).click();
  const header = item.locator('.copy-field', { hasText: 'Header Authorization' }).locator('code');
  const authorization = (await header.textContent())!.trim();
  expect(authorization).toMatch(/^Bearer pm_/);
  await expect(item.locator('.copy-field', { hasText: 'URL' }).locator('code')).toHaveText(
    `${baseURL}/api/v1/habits/${habit.id}/days/today`,
  );

  // The iOS shortcut sends neither cookies nor CSRF headers (a new context would inherit both from the config)
  const shortcut = await playwright.request.newContext({
    baseURL,
    storageState: { cookies: [], origins: [] },
    extraHTTPHeaders: {},
  });
  const tap = () =>
    shortcut.put(`/api/v1/habits/${habit.id}/days/today`, {
      headers: { Authorization: authorization },
      data: { done: true },
    });
  const first = await tap();
  expect(first.status()).toBe(200);
  expect(await first.json()).toMatchObject({ result: 'done', habit_name: name });
  expect((await first.json()).message).toContain(name);
  expect((await (await tap()).json()).result).toBe('already_done');

  await item.getByRole('button', { name: 'Fertig, Schlüssel ausblenden' }).click();
  await item.getByRole('button', { name: /Schlüssel .* widerrufen/ }).click();
  await expect.poll(async () => (await tap()).status()).toBe(401);
  await shortcut.dispose();
});
