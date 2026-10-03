import type { FollowUpBucket } from '@/api/follow-ups'

export const BUCKETS = [
  'needs_approval',
  'delivery_problem',
  'awaiting_contact',
  'awaiting_confirmation',
  'completed',
] as const satisfies readonly FollowUpBucket[]

export type Bucket = (typeof BUCKETS)[number]

export function isBucket(value: string): value is Bucket {
  return (BUCKETS as readonly string[]).includes(value)
}

export function bucketFromParams(params: URLSearchParams): Bucket | null {
  const value = params.get('bucket')?.trim()
  return value && isBucket(value) ? value : null
}

export function withBucket(
  params: URLSearchParams,
  bucket: Bucket | null,
): URLSearchParams {
  const next = new URLSearchParams(params)
  next.delete('page')
  if (bucket) next.set('bucket', bucket)
  else next.delete('bucket')
  return next
}
