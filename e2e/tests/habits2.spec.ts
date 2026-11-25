import { expect, test, type APIRequestContext } from '@playwright/test';
import { createHabit, today, todayRow, uniqueName } from './helpers';

function weekStart(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7));
  return date.toISOString().slice(0, 10);
}

interface DayJson {
  date: string;
  state: string;
  value: number | null;
  note: string | null;
}

async function dayOf(request: APIRequestContext, habitId: number, date: string): Promise<DayJson> {
  const response = await request.get(`/api/v1/days?from=${date}&to=${date}`);
  const data = (await response.json()) as { habits: { id: number; days: DayJson[] }[] };
  return data.habits.find((h) => h.id === habitId)!.days[0];
}

test('quantity goal: plus, minus and reaching the target', async ({ page, request }) => {
  const name = uniqueName('Wasser');
  const habit = await createHabit(request, name, { goal_type: 'quantity', target: 3, unit: 'Gläser' });
  const day = await today(request);
  await page.goto('/today');
  const row = todayRow(page, name);
  await expect(row).toContainText('0 von 3 Gläser');

  await row.getByRole('button', { name: `${name}: eins mehr` }).click();
  await row.getByRole('button', { name: `${name}: eins mehr` }).click();
  await expect(row).toContainText('2 von 3 Gläser');
  await expect(row).toContainText('Teilweise erledigt');
  await row.getByRole('button', { name: `${name}: eins weniger` }).click();
  await expect(row).toContainText('1 von 3 Gläser');
  await expect.poll(async () => (await dayOf(request, habit.id, day)).value).toBe(1);

  // A tap on the row sets the target
  await row.getByRole('button', { name: new RegExp(`auf das Ziel setzen`) }).click();
  await expect(row).toContainText('3 von 3 Gläser');
  await expect.poll(async () => (await dayOf(request, habit.id, day)).state).toBe('done');
});

test('weekly goal shows the week and counts any day', async ({ page, request }) => {
  const name = uniqueName('Laufen');
  // From Monday: a habit started mid-week gets a smaller target for its first week
  const monday = weekStart(await today(request));
  const habit = await createHabit(request, name, { goal_type: 'weekly_count', target: 3, start_on: monday });
  await page.goto('/today');
  const row = todayRow(page, name);
  await expect(row).toContainText('0 von 3 diese Woche');
  await row.getByRole('button', { name: new RegExp(name) }).first().click();
  await expect(row).toContainText('1 von 3 diese Woche');
  await expect.poll(async () => (await dayOf(request, habit.id, await today(request))).state).toBe('done');

  await page.goto('/week');
  await expect(page.getByRole('rowheader', { name: new RegExp(name) })).toContainText('1 von 3 diese Woche');
});

test('a pause takes the habit out of today', async ({ page, request }) => {
  const name = uniqueName('Dehnen');
  const habit = await createHabit(request, name);
  const day = await today(request);
  await page.goto('/habits');
  const pauses = page.getByRole('region', { name: 'Pausen' });
  await pauses.getByLabel('Für').selectOption({ label: name });
  await pauses.getByLabel('Von').fill(day);
  await pauses.getByLabel('Bis (einschließlich)').fill(day);
  await pauses.getByLabel('Grund (optional)').fill('Urlaub');
  await pauses.getByRole('button', { name: 'Pause eintragen' }).click();
  await expect(pauses.getByRole('listitem').filter({ hasText: name })).toContainText('Urlaub');
  await expect.poll(async () => (await dayOf(request, habit.id, day)).state).toBe('paused');

  await page.goto('/today');
  const paused = page.locator('details', { hasText: 'Pausiert' });
  await expect(paused).toBeVisible();
  await paused.locator('summary').click();
  await expect(todayRow(page, name)).toContainText('Pausiert');

  // Clean up so later tests are not affected
  await page.goto('/habits');
  await pauses.getByRole('button', { name: /Pause .* löschen/ }).first().click();
  await expect.poll(async () => (await dayOf(request, habit.id, day)).state).toBe('open');
});

test('a note is saved without touching the check-off', async ({ page, request }) => {
  const name = uniqueName('Notiz');
  const habit = await createHabit(request, name);
  const day = await today(request);
  await page.goto('/today');
  await todayRow(page, name).getByRole('button', { name: `${name}: Notiz` }).click();
  const dialog = page.getByRole('dialog', { name: new RegExp(`Notiz: ${name}`) });
  await dialog.getByLabel('Notiz (optional)').fill('Knie zwickt');
  await dialog.getByRole('button', { name: 'Notiz speichern' }).click();
  await expect(dialog).toBeHidden();
  await expect.poll(async () => (await dayOf(request, habit.id, day)).note).toBe('Knie zwickt');
  expect((await dayOf(request, habit.id, day)).state).toBe('open');
  await expect(todayRow(page, name).getByRole('button', { name: new RegExp(`${name}: Notiz \\(hat eine Notiz\\)`) })).toBeVisible();
});

test('sorting with the keyboard only', async ({ page, request }) => {
  const first = await createHabit(request, uniqueName('Erste'));
  const second = await createHabit(request, uniqueName('Zweite'));
  const order = async () => {
    const habits = (await (await request.get('/api/v1/habits')).json()) as { id: number }[];
    return habits.map((h) => h.id);
  };
  const before = await order();
  expect(before.indexOf(second.id)).toBe(before.indexOf(first.id) + 1);

  await page.goto('/habits');
  const handle = page.getByRole('button', { name: `${second.name} sortieren` });
  await handle.focus();
  await page.keyboard.press('Space');
  await expect(page.locator('.habit-item.is-dragging')).toHaveCount(1);
  await page.keyboard.press('ArrowUp');
  // dnd-kit announces the new position in its live region
  const position = before.indexOf(second.id) + 1;
  await expect(page.getByRole('status').filter({ hasText: `an Position ${position - 1} von` })).toBeAttached();
  await page.keyboard.press('Space');
  await expect.poll(async () => {
    const after = await order();
    return after.indexOf(second.id) < after.indexOf(first.id);
  }).toBe(true);
});

test('history shows the calendar with the day of a check-off', async ({ page, request }) => {
  const name = uniqueName('Verlauf');
  const habit = await createHabit(request, name);
  const day = await today(request);
  await request.put(`/api/v1/habits/${habit.id}/days/${day}`, { data: { done: true } });
  await page.goto('/history');
  await page.getByLabel('Gewohnheit').selectOption({ label: name });
  const calendar = page.getByRole('table', { name: new RegExp(name) });
  await expect(calendar).toBeVisible();
  const cell = calendar.getByRole('button', { name: /Erledigt/ }).first();
  await expect(cell).toBeVisible();
  await cell.click();
  await expect(page.getByText(/: Erledigt/).first()).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Quote je Zeitraum' })).toBeVisible();
});

test('an amount changed offline is sent when back online', async ({ page, context, request }) => {
  const name = uniqueName('Offline Menge');
  const habit = await createHabit(request, name, { goal_type: 'quantity', target: 5 });
  const day = await today(request);
  await page.goto('/today');
  const row = todayRow(page, name);
  await expect(row).toContainText('0 von 5');

  await context.setOffline(true);
  for (let i = 0; i < 3; i += 1) await row.getByRole('button', { name: `${name}: eins mehr` }).click();
  await expect(row).toContainText('3 von 5');
  await expect(row).toContainText('wartet auf Übertragung');
  expect((await dayOf(request, habit.id, day)).value).toBe(0);

  await context.setOffline(false);
  await expect(row).not.toContainText('wartet auf Übertragung');
  await expect.poll(async () => (await dayOf(request, habit.id, day)).value).toBe(3);
});
