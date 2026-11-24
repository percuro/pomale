import { expect, type APIRequestContext, type Page } from '@playwright/test';

export interface Habit {
  id: number;
  name: string;
}

let counter = 0;

/** Unique habit name per test run, so tests never see each other's data. */
export function uniqueName(prefix: string): string {
  counter += 1;
  return `${prefix} ${Date.now().toString(36)}${counter}`;
}

export async function createHabit(request: APIRequestContext, name: string, body: Record<string, unknown> = {}) {
  const response = await request.post('/api/v1/habits', { data: { name, ...body } });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as Habit;
}

export async function today(request: APIRequestContext): Promise<string> {
  const response = await request.get('/api/v1/auth/me');
  return ((await response.json()) as { today: string }).today;
}

export async function dayState(request: APIRequestContext, habitId: number, date: string) {
  const response = await request.get(`/api/v1/days?from=${date}&to=${date}`);
  const data = (await response.json()) as { habits: { id: number; days: { done: boolean; version: number }[] }[] };
  return data.habits.find((h) => h.id === habitId)!.days[0];
}

export async function setDay(request: APIRequestContext, habitId: number, date: string, done: boolean) {
  const response = await request.put(`/api/v1/habits/${habitId}/days/${date}`, { data: { done } });
  expect(response.ok(), await response.text()).toBeTruthy();
}

export function todayRow(page: Page, name: string) {
  return page.locator('li.today-row', { hasText: name });
}
