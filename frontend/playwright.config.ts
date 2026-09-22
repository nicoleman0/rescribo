import { defineConfig, devices } from '@playwright/test'

const externalServers = Boolean(process.env.PLAYWRIGHT_BASE_URL)

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173',
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
          command:
            'uv run python backend/manage.py migrate && uv run python backend/manage.py runserver 127.0.0.1:8000 --noreload',
          cwd: '..',
          url: 'http://127.0.0.1:8000/api/health/ready/',
          reuseExistingServer: !process.env.CI,
        },
        {
          command: 'npm run dev -- --host 127.0.0.1',
          url: 'http://127.0.0.1:5173',
          reuseExistingServer: !process.env.CI,
        },
      ],
})
