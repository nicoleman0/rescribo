import type { ApiError } from '@/api/request'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

function actionMessage(error: ApiError, record: string) {
  if (error.status === undefined) {
    return 'Could not reach Rescribo. Check your connection and try again.'
  }
  switch (error.reason) {
    case 'version_conflict':
      return `This ${record} changed while you were working. The latest version is shown; review it, then try again.`
    case 'invalid_transition':
      return `This action is no longer available for the ${record}. The latest version is shown.`
    case 'already_linked':
      return 'The report is already linked to this problem.'
    case 'no_changes':
      return 'Nothing changed.'
    case 'invalid_request':
    case 'invalid_reference':
    case 'title_required':
      return 'Check the highlighted fields.'
  }
  if (error.status === 404) {
    return `This ${record} no longer exists, or it belongs to another workspace.`
  }
  return error.message
}

/** Failure for a save or triage action. The form that owns the input keeps it. */
export function ActionError({
  error,
  title,
  record,
}: {
  error: ApiError
  title: string
  record: 'report' | 'problem'
}) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{actionMessage(error, record)}</AlertDescription>
    </Alert>
  )
}
