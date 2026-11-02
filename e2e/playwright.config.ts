import { defineConfig, devices } from '@playwright/test'

// Runs against a live API + UI on E2E_BASE_URL. In CI that is uvicorn with FAKE_LLM=true:
// a scripted model, but the real Docker sandbox, test harness, repair loop and SSE stream.
export default defineConfig({
  testDir: './tests',
  timeout: 90_000,
  expect: { timeout: 30_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    // Locally you can reuse an installed browser: PW_CHANNEL=chrome npm test
    ...(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {}),
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, grep: /@mobile/ },
  ],
})
