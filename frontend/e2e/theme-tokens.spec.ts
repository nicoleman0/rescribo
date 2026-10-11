import { expect, test } from '@playwright/test'

// Each token's colour before the palette variables existed for issue 197: [light, dark].
const REFERENCE: Record<string, [string, string]> = {
  '--background': ['fbfbfc', '0f0f14'],
  '--sidebar': ['f4f4f7', '131319'],
  '--card': ['ffffff', '17171f'],
  '--raised': ['ffffff', '1c1c25'],
  '--raised-muted': ['f4f4f7', '24242e'],
  '--card-foreground': ['16161d', 'ececf1'],
  '--border': ['e4e4ea', '26262f'],
  '--foreground': ['16161d', 'ececf1'],
  '--muted-foreground': ['62626e', 'a0a0ae'],
  '--muted': ['f4f4f7', '1d1d26'],
  '--secondary': ['f4f4f7', '1d1d26'],
  '--secondary-foreground': ['16161d', 'ececf1'],
  '--accent': ['f4f4f7', '1d1d26'],
  '--accent-foreground': ['16161d', 'ececf1'],
  '--input': ['e4e4ea', '34343f'],
  '--selected': ['ececf3', '23233a'],
  '--primary': ['5b5bd6', '8b8cf5'],
  '--primary-foreground': ['ffffff', '101018'],
  '--destructive': ['b42318', 'ffa399'],
  '--destructive-foreground': ['ffffff', '101018'],
  '--ring': ['5b5bd6', '8b8cf5'],
  '--tone-neutral': ['f0f0f4', '24242d'],
  '--tone-neutral-foreground': ['4b4b57', 'b8b8c5'],
  '--tone-neutral-dot': ['9a9aa6', '7a7a88'],
  '--tone-info': ['ebebfd', '24244a'],
  '--tone-info-foreground': ['3f3fb0', 'b2b2ff'],
  '--tone-info-dot': ['5b5bd6', '8b8cf5'],
  '--tone-progress': ['e6f0fb', '142a42'],
  '--tone-progress-foreground': ['1d5ca3', '92c2f5'],
  '--tone-progress-dot': ['3b82d6', '5aa2ec'],
  '--tone-success': ['e3f3ea', '12301f'],
  '--tone-success-foreground': ['17613f', '84d8a8'],
  '--tone-success-dot': ['2f9e64', '3fbf7a'],
  '--tone-warning': ['fbeedb', '3a2a11'],
  '--tone-warning-foreground': ['8a4b00', 'f2bd66'],
  '--tone-warning-dot': ['d98a1c', 'e6a23c'],
  '--tone-danger': ['fde8e6', '3f1915'],
  '--tone-danger-foreground': ['b42318', 'ffa399'],
  '--tone-danger-dot': ['e0483a', 'f0675a'],
}

// Fixed tokens must match exactly. Derived tokens may round by one step per channel.
const FIXED = /^--(tone-|destructive$)/

const channels = (hex: string) =>
  [0, 2, 4].map((start) => parseInt(hex.slice(start, start + 2), 16))

for (const [index, theme] of (['light', 'dark'] as const).entries()) {
  test(`${theme} colour tokens match their original values`, async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: theme })
    await page.goto('/sign-in')
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)

    // Computed colour text may use OKLCH notation, so read the painted sRGB pixel.
    const painted = await page.evaluate((tokens) => {
      const probe = document.createElement('div')
      document.body.append(probe)
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 1
      const context = canvas.getContext('2d', { willReadFrequently: true })!
      const result: Record<string, number[]> = {}
      for (const token of tokens) {
        probe.style.backgroundColor = `var(${token})`
        context.clearRect(0, 0, 1, 1)
        context.fillStyle = getComputedStyle(probe).backgroundColor
        context.fillRect(0, 0, 1, 1)
        result[token] = [...context.getImageData(0, 0, 1, 1).data]
      }
      probe.remove()
      return result
    }, Object.keys(REFERENCE))

    let exact = 0
    let offByOne = 0
    const wrong = Object.entries(REFERENCE).flatMap(([token, hexes]) => {
      const want = channels(hexes[index])
      const [red, green, blue, alpha] = painted[token]
      const error = Math.max(
        ...[red, green, blue].map((value, i) => Math.abs(value - want[i])),
      )
      const allowed = FIXED.test(token) ? 0 : 1
      if (error === 0) exact += 1
      else if (error === 1) offByOne += 1
      return alpha === 255 && error <= allowed
        ? []
        : [`${token}: wanted ${hexes[index]}, painted ${painted[token]}`]
    })
    console.info(`${theme}: ${exact} exact, ${offByOne} off by 1/255`)
    expect(wrong).toEqual([])
  })
}
