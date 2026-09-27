export type ApiError = Error & {
  status?: number
  reason?: string
  fieldErrors?: Record<string, string[]>
  /** The current record returned with a 409. API modules narrow its type. */
  current?: unknown
}

function csrfToken(): string | undefined {
  return document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith('csrftoken='))
    ?.slice('csrftoken='.length)
}

export async function apiRequest<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    credentials: 'same-origin',
    headers: {
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(body === undefined || !csrfToken()
        ? {}
        : { 'X-CSRFToken': decodeURIComponent(csrfToken()!) }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as {
      detail?: string
      reason?: string
      field_errors?: Record<string, string[]>
      current?: unknown
    }
    const error = new Error(payload.detail ?? 'The request failed.') as ApiError
    error.status = response.status
    error.reason = payload.reason
    error.fieldErrors = payload.field_errors
    error.current = payload.current
    throw error
  }
  return (response.status === 204 ? undefined : response.json()) as Promise<T>
}

/** Encode defined, non-empty values as a query string with a leading `?`. */
export function queryString(
  query: Record<string, string | number | undefined>,
): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}
