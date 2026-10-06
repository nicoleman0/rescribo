import { defineConfig, loadEnv } from 'vite'
import { copy } from './src/copy.ts'

function httpsUrl(value: string | undefined, name: string): string | undefined {
  if (!value) return undefined
  let url: URL
  try {
    url = new URL(value)
  } catch {
    throw new Error(`${name} must be an absolute HTTPS URL`)
  }
  if (url.protocol !== 'https:' || url.username || url.password) {
    throw new Error(`${name} must be an HTTPS URL without credentials`)
  }
  return url.href
}

function escape(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[character]!
  })
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'MARKETING_')
  const siteUrl = httpsUrl(env.MARKETING_SITE_URL, 'MARKETING_SITE_URL')
  return {
    base: './',
    plugins: [
      {
        name: 'marketing-content',
        transformIndexHtml: {
          order: 'pre',
          handler: (html) =>
            html.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => {
              if (key === 'canonical')
                return siteUrl
                  ? `<link rel="canonical" href="${escape(siteUrl)}">`
                  : ''
              if (key in copy) return escape(copy[key as keyof typeof copy])
              throw new Error(`Unknown marketing content token: ${key}`)
            }),
        },
      },
    ],
  }
})
