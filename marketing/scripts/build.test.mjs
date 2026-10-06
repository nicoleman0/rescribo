import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { readFileSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { checkLinks } from './check-links.mjs'

function build(values = {}) {
  const env = {
    ...process.env,
    MARKETING_APP_URL: '',
    MARKETING_SITE_URL: '',
    ...values,
  }
  execFileSync(process.execPath, ['node_modules/vite/bin/vite.js', 'build'], {
    env,
    stdio: 'pipe',
  })
  return readFileSync('dist/index.html', 'utf8')
}
test('unconfigured build is public; configured links are static HTML', () => {
  assert.doesNotMatch(build(), /Sign in|rel="canonical"|not configured|\{\{/)
  const html = build({
    MARKETING_APP_URL:
      'https://app.example.org/login?from=marketing&next=inbox',
    MARKETING_SITE_URL: 'https://www.example.org/',
  })
  assert.match(
    html,
    /href="https:\/\/app.example.org\/login\?from=marketing&amp;next=inbox"/,
  )
  assert.match(html, /rel="canonical" href="https:\/\/www.example.org\/"/)
})
test('invalid supplied URLs fail clearly', () => {
  for (const name of ['MARKETING_APP_URL', 'MARKETING_SITE_URL']) {
    for (const value of [
      'http://example.org',
      '/login',
      'https://user:secret@example.org',
    ]) {
      assert.throws(
        () => build({ [name]: value }),
        (error) => String(error.stderr).includes(`${name} must be`),
      )
    }
  }
})
test('link checker detects missing fragments and assets', async () => {
  const root = mkdtempSync(join(tmpdir(), 'rescribo-links-'))
  try {
    writeFileSync(join(root, 'index.html'), '<a href="#missing">broken</a>')
    await assert.rejects(checkLinks(root), /Missing fragment/)
    writeFileSync(join(root, 'index.html'), '<img src="./missing.png">')
    await assert.rejects(checkLinks(root), /ENOENT/)
    writeFileSync(
      join(root, 'index.html'),
      '<a href="http://example.org">broken</a>',
    )
    await assert.rejects(checkLinks(root), /Unexpected link scheme/)
  } finally {
    rmSync(root, { recursive: true })
  }
})
// Browser checks use the caller's configuration after the build probes.
test('restore requested build for browser checks', () => {
  build({
    MARKETING_APP_URL: process.env.MARKETING_APP_URL ?? '',
    MARKETING_SITE_URL: process.env.MARKETING_SITE_URL ?? '',
  })
})
