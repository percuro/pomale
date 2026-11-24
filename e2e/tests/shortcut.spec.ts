import { expect, test } from '@playwright/test';
import { createHabit, uniqueName } from './helpers';

test('shortcut key checks off today and stops working after revoking', async ({ page, request, playwright, baseURL }) => {
  const name = uniqueName('Wasser');
  const habit = await createHabit(request, name);
  await page.goto('/gewohnheiten');
  const item = page.locator('li.habit-item', { hasText: name });
  await item.getByRole('button', { name: 'Kurzbefehl', exact: true }).click();
  await item.getByRole('button', { name: 'Schlüssel anlegen' }).click();
  const header = item.locator('.copy-field', { hasText: 'Header Authorization' }).locator('code');
  const authorization = (await header.textContent())!.trim();
  expect(authorization).toMatch(/^Bearer ht_/);
  await expect(item.locator('.copy-field', { hasText: 'URL' }).locator('code')).toHaveText(
    `${baseURL}/api/v1/habits/${habit.id}/days/today`,
  );

  // The iOS shortcut sends neither cookies nor CSRF headers
  const shortcut = await playwright.request.newContext({ baseURL });
  const tap = () =>
    shortcut.put(`/api/v1/habits/${habit.id}/days/today`, {
      headers: { Authorization: authorization },
      data: { done: true },
    });
  const first = await tap();
  expect(first.status()).toBe(200);
  expect((await first.json()).message).toBe(`${name}: Heute erledigt`);
  expect((await (await tap()).json()).status).toBe('Bereits erledigt');

  await item.getByRole('button', { name: 'Fertig, Schlüssel ausblenden' }).click();
  await item.getByRole('button', { name: /Schlüssel .* widerrufen/ }).click();
  await expect.poll(async () => (await tap()).status()).toBe(401);
  await shortcut.dispose();
});
