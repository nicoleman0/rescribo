import type { ApiError } from '@/api/request'

const fieldMessages: Record<string, string> = {
  invalid_reference: 'Choose an active record in this workspace.',
  title_required: 'Enter a title.',
}

/** The first error for a form field, in words a member can act on. */
export function fieldError(error: ApiError | null, field: string) {
  const message = error?.fieldErrors?.[field]?.[0]
  return message ? (fieldMessages[message] ?? message) : undefined
}
