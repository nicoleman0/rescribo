import type { ApiError } from '@/api/request'

const fieldMessages: Record<string, string> = {
  invalid_reference: 'Choose an active record in this workspace.',
  title_required: 'Enter a title.',
}

const asked = new WeakMap<ApiError, Set<string>>()

/** The first error for a form field, in words a member can act on. */
export function fieldError(error: ApiError | null, field: string) {
  if (!error) return undefined
  let fields = asked.get(error)
  if (!fields) {
    fields = new Set()
    asked.set(error, fields)
  }
  // Record reads so the summary knows what the form asked about.
  fields.add(field)
  const message = error?.fieldErrors?.[field]?.[0]
  return message ? (fieldMessages[message] ?? message) : undefined
}

const noField = 'non_field_errors'

function fieldLabel(field: string) {
  const words = field.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** One line per field error that no `fieldError` call asked for. */
export function unrenderedFieldErrors(error: ApiError): string[] {
  const fields = asked.get(error)
  return Object.entries(error.fieldErrors ?? {}).flatMap(
    ([field, messages]) => {
      if (fields?.has(field)) return []
      const text = messages
        .map((message) => fieldMessages[message] ?? message)
        .filter(
          (message) => message !== error.reason && message !== error.message,
        )
        .join(' ')
      if (!text) return []
      return [field === noField ? text : `${fieldLabel(field)}: ${text}`]
    },
  )
}
