import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { listProblems, problemKeys } from '@/api/problems'
import { listReports, reportKeys } from '@/api/reports'

export const PALETTE_MIN_CHARS = 2
export const PALETTE_DEBOUNCE_MS = 200
export const PALETTE_ROWS = 5

/** Searches reports and problems with the same `q` the inbox and problems
 * list use, so the palette agrees with both pages. */
export function usePaletteSearch(
  workspaceId: string,
  text: string,
  open: boolean,
) {
  const term = text.trim()
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term), PALETTE_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [term])

  const active = term.length >= PALETTE_MIN_CHARS
  const settled = debounced === term
  const enabled = open && active && settled
  const reports = useQuery({
    queryKey: reportKeys.list(workspaceId, { q: debounced }),
    queryFn: () => listReports(workspaceId, { q: debounced }),
    enabled,
    retry: false,
  })
  const problems = useQuery({
    queryKey: problemKeys.list(workspaceId, { q: debounced }),
    queryFn: () => listProblems(workspaceId, { q: debounced }),
    enabled,
    retry: false,
  })

  const group = <T>(query: {
    data?: { results: T[] }
    isError: boolean
    isFetching: boolean
    refetch: () => unknown
  }) => ({
    rows: query.data?.results.slice(0, PALETTE_ROWS) ?? [],
    searching: active && (!settled || query.isFetching),
    failed: active && settled && query.isError && !query.isFetching,
    retry: () => void query.refetch(),
  })
  const reportGroup = group(reports)
  const problemGroup = group(problems)
  return {
    active,
    reports: reportGroup,
    problems: problemGroup,
    searching: reportGroup.searching || problemGroup.searching,
  }
}
