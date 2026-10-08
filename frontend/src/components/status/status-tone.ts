export const STATUS_TONES = [
  'neutral',
  'info',
  'progress',
  'success',
  'warning',
  'danger',
] as const

export type StatusTone = (typeof STATUS_TONES)[number]

/** Background and text for a surface in each tone. Literal class strings so
 * Tailwind can find them. */
export const toneSurfaceClasses: Record<StatusTone, string> = {
  neutral: 'bg-tone-neutral text-tone-neutral-foreground',
  info: 'bg-tone-info text-tone-info-foreground',
  progress: 'bg-tone-progress text-tone-progress-foreground',
  success: 'bg-tone-success text-tone-success-foreground',
  warning: 'bg-tone-warning text-tone-warning-foreground',
  danger: 'bg-tone-danger text-tone-danger-foreground',
}
