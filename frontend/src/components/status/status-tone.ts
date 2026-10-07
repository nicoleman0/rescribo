export const STATUS_TONES = [
  'neutral',
  'info',
  'progress',
  'success',
  'warning',
  'danger',
] as const

export type StatusTone = (typeof STATUS_TONES)[number]
