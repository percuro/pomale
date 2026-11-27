import { defineConfig, devices } from '@playwright/test';

/**
 * Screenshots for the README and docs/screenshots.md, taken by hand (not in CI) from an instance
 * with DEMO_MODE=true, so they always show the same sample data:
 *
 *   docker run --rm -d --name pomale-shots -p 8020:8000 -e PUBLIC_URL=http://localhost:8020 -e DEMO_MODE=true ghcr.io/percuro/pomale:1
 *   E2E_DEMO_URL=http://localhost:8020 npx playwright test -c screenshots/screenshots.config.ts
 *
 * The PNG files are written to docs/screenshots/.
 */
const baseURL = process.env.E2E_DEMO_URL ?? 'http://localhost:8020';

export default defineConfig({
  testDir: '.',
  testMatch: 'screenshots.spec.ts',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL,
    extraHTTPHeaders: { 'X-Habit-CSRF': '1', Origin: baseURL },
    locale: 'en-GB',
    timezoneId: 'UTC',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 860 }, deviceScaleFactor: 1 } },
    // Chromium with the size of an iPhone: WebKit is not needed for a picture
    { name: 'phone', use: { ...devices['iPhone 15'], browserName: 'chromium', deviceScaleFactor: 2 } },
  ],
});
