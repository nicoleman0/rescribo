import { Fragment } from 'react'
import type { ApiError } from '@/api/request'
import { unrenderedFieldErrors } from './field-error'

/**
 * A form's failure text, then the errors for fields it does not render.
 * Direct field queries count even when this summary appears above them in JSX.
 */
export function FormErrorMessage({
  error,
  message = error.message,
}: {
  error: ApiError
  message?: string
}) {
  return (
    <>
      {message}
      {unrenderedFieldErrors(error).map((line) => (
        <Fragment key={line}>
          {' '}
          <span className="block">{line}</span>
        </Fragment>
      ))}
    </>
  )
}
