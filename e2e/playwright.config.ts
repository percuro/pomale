import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests against a running instance (usually the built image).
 * E2E_BASE_URL  e.g. http://localhost:8000 (must equal the instance's PUBLIC_URL)
 * E2E_SETUP_TOKEN  setup token from the server log, for a fresh instance
 * E2E_USERNAME / E2E_PASSWORD  account to create (fresh) or log in with
 * E2E_OIDC=1  Dex runs with e2e/oidc/dex.yaml and the instance has OIDC_LABEL=Dex (else OIDC tests are skipped)
 * E2E_BASE_URL_2 / E2E_SETUP_TOKEN_2  second instance with PASSWORD_LOGIN=off and OIDC_AUTO_CREATE=on
 * E2E_BASE_URL_3  third instance with DEMO_MODE=true
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:8000';

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts',
  // One shared instance and account: run serially to keep tests independent of order
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    storageState: '.auth/state.json',
    extraHTTPHeaders: { 'X-Habit-CSRF': '1', Origin: baseURL },
    trace: 'retain-on-failure',
    locale: 'de-AT',
    timezoneId: 'UTC',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'iphone-webkit', use: { ...devices['iPhone 15'] } },
  ],
});
