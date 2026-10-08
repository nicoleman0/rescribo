import { useId, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  linkFixRelease,
  listReleases,
  problemKeys,
  type ProblemDetail,
  type ReleaseOption,
} from '@/api/problems'
import type { ApiError } from '@/api/request'
import { Field } from '@/components/forms/field'
import { Button } from '@/components/ui/button'
import {
  ErrorState,
  LoadingState,
  ReadyState,
} from '@/components/states/async-states'
import { formatDate } from '@/features/inbox/report-format'
import { useProblemMutation } from './use-problem-mutation'

export function ReleasePicker({
  workspaceId,
  problem,
  onCancel,
}: {
  workspaceId: string
  problem: ProblemDetail
  onCancel: () => void
}) {
  const id = useId()
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState('')
  const query = useInfiniteQuery({
    queryKey: [...problemKeys.releases(workspaceId), 'picker'],
    queryFn: ({ pageParam }) => listReleases(workspaceId, pageParam),
    initialPageParam: 1,
    getNextPageParam: (lastPage, pages) =>
      lastPage.has_next ? pages.length + 1 : undefined,
  })
  const mutation = useProblemMutation(
    workspaceId,
    (input: { external_id: string }) =>
      linkFixRelease(workspaceId, problem.id, {
        expected_version: problem.version,
        ...input,
      }),
    onCancel,
  )
  const rows = query.data?.pages.flatMap((page) => page.results) ?? []
  const shown = rows.filter((row) =>
    `${row.tag_name} ${row.name}`
      .toLocaleLowerCase()
      .includes(filter.toLocaleLowerCase()),
  )
  const error = query.error as ApiError | null
  const reason = error?.reason

  return (
    <section
      aria-label="Link a release"
      className="animate-panel-enter grid gap-3 rounded-card border border-border p-4"
    >
      <h3 className="text-sm font-semibold">Choose a release</h3>
      {query.isPending ? <LoadingState label="Loading releases" /> : null}
      {error && reason === 'connection_not_ready' ? (
        <p role="alert">
          Connect GitHub in workspace settings to link a release.{' '}
          <Link className="underline" to="/settings">
            Open settings
          </Link>
        </p>
      ) : null}
      {error && reason === 'release_access_missing' ? (
        <p role="alert">
          The GitHub App installation needs Contents read access. Ask the
          installation owner to accept the new permission.
        </p>
      ) : null}
      {error && reason === 'release_provider_unavailable' ? (
        <ErrorState
          title="Could not load releases"
          onRetry={() => void query.refetch()}
          isRetrying={query.isFetching}
        />
      ) : null}
      {query.isError &&
      ![
        'connection_not_ready',
        'release_access_missing',
        'release_provider_unavailable',
      ].includes(reason ?? '') ? (
        <ErrorState
          title="Could not load releases"
          onRetry={() => void query.refetch()}
          isRetrying={query.isFetching}
        />
      ) : null}
      {query.data ? (
        <ReadyState className="grid gap-3">
          <Field
            id={`${id}-filter`}
            label="Filter loaded releases"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
          <fieldset
            className="stagger-rows grid max-h-64 gap-2 overflow-y-auto"
            aria-label="Releases"
          >
            {shown.map((release) => (
              <ReleaseRow
                key={release.external_id}
                release={release}
                selected={selected === release.external_id}
                onSelect={() => setSelected(release.external_id)}
              />
            ))}
            {!shown.length ? (
              <p className="text-sm text-muted-foreground">
                No matching releases.
              </p>
            ) : null}
          </fieldset>
          {query.hasNextPage ? (
            <Button
              type="button"
              variant="outline"
              onClick={() => void query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
            >
              {query.isFetchingNextPage ? 'Loading…' : 'Load more'}
            </Button>
          ) : null}
        </ReadyState>
      ) : null}
      {mutation.error ? (
        <p role="alert">
          {mutation.error.reason === 'connection_not_ready'
            ? 'Connect GitHub in workspace settings to link a release.'
            : mutation.error.reason === 'release_access_missing'
              ? 'The GitHub App installation needs Contents read access. Ask the installation owner to accept the new permission.'
              : mutation.error.reason === 'release_provider_unavailable'
                ? 'GitHub releases are temporarily unavailable. Try again.'
                : mutation.error.message}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          onClick={() => mutation.mutate({ external_id: selected })}
          disabled={!selected || mutation.isPending}
        >
          {mutation.isPending ? 'Linking…' : 'Link release'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={mutation.isPending}
        >
          Cancel
        </Button>
      </div>
    </section>
  )
}

function ReleaseRow({
  release,
  selected,
  onSelect,
}: {
  release: ReleaseOption
  selected: boolean
  onSelect: () => void
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-card border border-border p-3">
      <input
        type="radio"
        name="fix-release"
        value={release.external_id}
        checked={selected}
        onChange={onSelect}
        className="mt-1"
      />
      <span className="grid min-w-0 gap-1">
        <span className="flex flex-wrap items-center gap-2 font-medium">
          {release.tag_name}
          {release.name !== release.tag_name ? (
            <span className="font-normal text-muted-foreground">
              {release.name}
            </span>
          ) : null}
          {release.prerelease ? (
            <span className="rounded-pill bg-selected px-2 py-0.5 text-xs">
              Pre-release
            </span>
          ) : null}
        </span>
        <time
          className="text-xs text-muted-foreground"
          dateTime={release.published_at}
        >
          {formatDate(release.published_at)}
        </time>
      </span>
    </label>
  )
}
