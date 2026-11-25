import { expect, type APIRequestContext, type Browser, type BrowserContext, type Page } from '@playwright/test';

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

export interface Account {
  context: BrowserContext;
  page: Page;
  username: string;
  password: string;
  id: number;
}

let accountCounter = 0;

/**
 * A browser without the admin's session: in Playwright Test, browser.newContext() would
 * otherwise inherit the project's storageState.
 */
export function freshContext(
  browser: Browser,
  baseURL: string,
  options: { locale?: string; timezoneId?: string; apiHeaders?: boolean } = {},
): Promise<BrowserContext> {
  return browser.newContext({
    baseURL,
    storageState: { cookies: [], origins: [] },
    locale: options.locale ?? 'de-AT',
    timezoneId: options.timezoneId ?? 'UTC',
    extraHTTPHeaders: options.apiHeaders ? { 'X-Habit-CSRF': '1', Origin: baseURL } : {},
  });
}

/** A one-time link created by the admin (the default e2e account is the instance's first admin). */
export async function createLink(admin: APIRequestContext, path = '/api/v1/admin/invitations', data = {}) {
  const response = await admin.post(path, { data });
  expect(response.status(), await response.text()).toBe(201);
  return ((await response.json()) as { url: string }).url;
}

/** A second account in its own browser (own cookies), created through an invitation. */
export async function newAccount(
  browser: Browser,
  admin: APIRequestContext,
  baseURL: string,
  options: { locale?: string; timezoneId?: string; accountTimezone?: string | null } = {},
): Promise<Account> {
  const url = await createLink(admin);
  const token = url.split('#')[1];
  accountCounter += 1;
  const username = `u${Date.now().toString(36)}${accountCounter}`;
  const password = 'zweites-passwort-123';
  const context = await freshContext(browser, baseURL, { ...options, apiHeaders: true });
  const response = await context.request.post('/api/v1/invitations/accept', {
    data: { token, username, password, timezone: options.accountTimezone ?? null },
  });
  expect(response.status(), await response.text()).toBe(200);
  const { id } = (await response.json()) as { id: number };
  return { context, page: await context.newPage(), username, password, id };
}
