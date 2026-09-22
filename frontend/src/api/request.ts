export type ApiError = Error & {
  reason?: string
  fieldErrors?: Record<string, string[]>
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
    }
    const error = new Error(payload.detail ?? 'The request failed.') as ApiError
    error.reason = payload.reason
    error.fieldErrors = payload.field_errors
    throw error
  }
  return (response.status === 204 ? undefined : response.json()) as Promise<T>
}
