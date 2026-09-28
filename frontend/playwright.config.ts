import { defineConfig, devices } from '@playwright/test'

const externalServers = Boolean(process.env.PLAYWRIGHT_BASE_URL)
const apiPort = process.env.RESCRIBO_E2E_API_PORT ?? '8000'
const frontendPort = process.env.RESCRIBO_E2E_FRONTEND_PORT ?? '5173'
const frontendUrl = `http://127.0.0.1:${frontendPort}`

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? frontendUrl,
    trace: 'retain-on-failure',
  },
  projects: externalServers
    ? [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
    : [
        { name: 'setup', testMatch: /.*\.setup\.ts/ },
        {
          name: 'chromium',
          use: { ...devices['Desktop Chrome'] },
          dependencies: ['setup'],
        },
      ],
  webServer: externalServers
    ? []
    : [
        {
          command: `uv run python backend/manage.py migrate && uv run python backend/manage.py runserver 127.0.0.1:${apiPort} --noreload`,
          cwd: '..',
          url: `http://127.0.0.1:${apiPort}/api/health/ready/`,
          reuseExistingServer: !process.env.CI,
        },
        {
          command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
          env: { API_PROXY_TARGET: `http://127.0.0.1:${apiPort}` },
          url: frontendUrl,
          reuseExistingServer: !process.env.CI,
        },
      ],
})
