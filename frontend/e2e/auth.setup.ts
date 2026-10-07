import { execFileSync } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test as setup } from '@playwright/test'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const authDir = path.join(path.dirname(fileURLToPath(import.meta.url)), '.auth')

setup('seed accounts for browser journeys', async () => {
  const output = execFileSync(
    'uv',
    ['run', 'python', 'backend/manage.py', 'seed_test_accounts', '--json'],
    {
      cwd: root,
      encoding: 'utf8',
    },
  )
  await mkdir(authDir, { recursive: true })
  await writeFile(path.join(authDir, 'seed.json'), output)
})

setup('seed the demo workspace', async () => {
  const output = execFileSync(
    'uv',
    ['run', 'python', 'backend/manage.py', 'seed_demo', '--json'],
    {
      cwd: root,
      encoding: 'utf8',
      env: {
        ...process.env,
        RESCRIBO_DEMO_PASSWORD:
          process.env.RESCRIBO_DEMO_PASSWORD ?? 'Rescribo-demo-e2e-2026!',
      },
    },
  )
  await mkdir(authDir, { recursive: true })
  await writeFile(path.join(authDir, 'demo.json'), output)
})
