/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { APP_NAME, APP_SHORT_NAME, BACKGROUND_COLOR, THEME_COLOR, THEME_COLOR_DARK } from './src/app/brand.ts'

const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8')) as {
  version: string
}

/** Fills %APP_NAME%-style placeholders in index.html and emits the web app manifest. */
function brand(): Plugin {
  const values: Record<string, string> = { APP_NAME, APP_SHORT_NAME, THEME_COLOR, THEME_COLOR_DARK }
  return {
    name: 'brand',
    transformIndexHtml: (html) => html.replace(/%(APP_NAME|APP_SHORT_NAME|THEME_COLOR_DARK|THEME_COLOR)%/g, (_, key) => values[key]),
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: 'manifest.webmanifest',
        source: JSON.stringify(
          {
            name: APP_NAME,
            short_name: APP_SHORT_NAME,
            start_url: '/',
            scope: '/',
            display: 'standalone',
            background_color: BACKGROUND_COLOR,
            theme_color: THEME_COLOR,
            icons: [
              { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
              { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
              { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
              { src: '/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
            ],
          },
          null,
          2,
        ),
      })
    },
  }
}

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(version),
  },
  plugins: [
    react(),
    brand(),
    // Own service worker (src/sw.ts): caches the app shell and shows reminders. API responses
    // never come from the SW cache; day lists and the change queue live in IndexedDB.
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      injectRegister: 'script',
      manifest: false,
      injectManifest: {
        globPatterns: ['**/*.{js,css,html,svg,png,webmanifest}'],
      },
    }),
  ],
  test: {
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.ts'],
    // styles/tokens.test.ts reads theme.css as text; without this, style files are empty in tests
    css: true,
  },
  // Development: the backend (uvicorn app.web:application) serves /api like in production
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
