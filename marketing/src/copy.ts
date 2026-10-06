import { readFileSync } from 'node:fs'

// README owns workflow copy; OpenSpec context supplies the audience.
const readme = readFileSync(new URL('../../README.md', import.meta.url), 'utf8')
function required(pattern: RegExp, name: string): string {
  const value = readme.match(pattern)?.[1]
  if (!value) throw new Error(`README is missing marketing copy: ${name}`)
  return value
}

export const copy = {
  headline: required(/^# (.+)$/m, 'headline'),
  introduction: required(
    /^(Rescribo is being built[^\n]+)$/m,
    'introduction',
  ).replace('is being built to help', 'helps'),
  capture: required(/^- \*\*Capture:\*\* (.+)$/m, 'Capture'),
  connect: required(/^- \*\*Connect:\*\* (.+)$/m, 'Connect'),
  followUp: required(/^- \*\*Follow up:\*\* (.+)$/m, 'Follow up'),
}
