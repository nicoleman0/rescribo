import { readFile, access } from 'node:fs/promises'
import { resolve, dirname, sep } from 'node:path'
import { pathToFileURL } from 'node:url'

export async function checkLinks(root, { live = false } = {}) {
  const file = resolve(root, 'index.html')
  const html = await readFile(file, 'utf8')
  const ids = new Set(
    [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]),
  )
  const urls = new Set(
    [...html.matchAll(/\b(?:href|src)="([^"]+)"/g)].map((match) =>
      match[1].replaceAll('&amp;', '&'),
    ),
  )
  if (/\{\{\w+\}\}/.test(html))
    throw new Error('Unresolved template token in built HTML')
  for (const value of urls) {
    if (value.startsWith('https:')) {
      const url = new URL(value)
      if (live) {
        let response = await fetch(url, {
          method: 'HEAD',
          signal: AbortSignal.timeout(15000),
        })
        if (response.status === 405)
          response = await fetch(url, { signal: AbortSignal.timeout(15000) })
        if (!response.ok)
          throw new Error(
            `Broken external link: ${url.href} (${response.status})`,
          )
      }
    } else if (value.startsWith('#')) {
      if (value.length > 1 && !ids.has(value.slice(1)))
        throw new Error(`Missing fragment: ${value}`)
    } else {
      const url = new URL(value, 'https://local.invalid/')
      if (url.origin !== 'https://local.invalid')
        throw new Error(`Unexpected link scheme: ${value}`)
      const asset = resolve(
        dirname(file),
        decodeURIComponent(url.pathname.slice(1)),
      )
      if (!asset.startsWith(resolve(root) + sep))
        throw new Error(`Link escapes build directory: ${value}`)
      await access(asset)
    }
  }
  return urls.size
}
if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  const count = await checkLinks(resolve('dist'), {
    live: process.argv.includes('--live'),
  })
  console.log(
    `Checked ${count} links and assets${process.argv.includes('--live') ? ' including live HTTPS destinations' : ' (external HTTPS destinations validated structurally)'}.`,
  )
}
