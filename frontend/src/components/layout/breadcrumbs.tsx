import { useQuery } from '@tanstack/react-query'
import { matchPath, Link, useLocation } from 'react-router-dom'
import { getProblem, problemKeys } from '@/api/problems'
import { getFollowUp, followUpKeys } from '@/api/follow-ups'
import { useOptionalWorkspace } from '@/components/auth/use-workspace'
import { settingsSections } from '@/features/settings/sections'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'

const paths = [
  ['/inbox/new', 'Inbox', 'New report'],
  ['/inbox/:reportId', 'Inbox'],
  ['/inbox', 'Inbox'],
  ['/problems/:problemId', 'Problems'],
  ['/problems', 'Problems'],
  ['/follow-ups/:followUpId/page', 'Follow-ups', 'follow-up'],
  ['/follow-ups/:followUpId', 'Follow-ups'],
  ['/follow-ups', 'Follow-ups'],
  ['/dev/ui', 'UI gallery'],
] as const

export function Breadcrumbs() {
  const { pathname } = useLocation()
  const workspace = useOptionalWorkspace()
  const workspaceId = workspace?.workspace.id
  const problemMatch = matchPath('/problems/:problemId', pathname)
  const followUpMatch = matchPath('/follow-ups/:followUpId/page', pathname)
  const problemId = problemMatch?.params.problemId
  const followUpId = followUpMatch?.params.followUpId
  const settingsSlug = pathname.match(/^\/settings\/([^/]+)$/)?.[1]
  const settingsSection = settingsSections.find(
    ({ slug }) => slug === settingsSlug,
  )
  const problem = useQuery({
    queryKey:
      problemId && workspaceId
        ? problemKeys.detail(workspaceId, problemId)
        : ['breadcrumb', 'problem'],
    queryFn: () => getProblem(workspaceId!, problemId!),
    enabled: Boolean(problemId && workspaceId),
  })
  const followUp = useQuery({
    queryKey:
      followUpId && workspaceId
        ? followUpKeys.detail(workspaceId, followUpId)
        : ['breadcrumb', 'follow-up'],
    queryFn: () => getFollowUp(workspaceId!, followUpId!),
    enabled: Boolean(followUpId && workspaceId),
  })
  const selected = settingsSection
    ? undefined
    : paths.find(([path]) => matchPath({ path, end: true }, pathname))
  if (settingsSection) {
    return (
      <Breadcrumb aria-label="Breadcrumb">
        <BreadcrumbList className="min-w-0 flex-nowrap overflow-hidden">
          <BreadcrumbItem className="shrink-0">
            <BreadcrumbLink asChild>
              <Link to="/settings">Settings</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem className="min-w-0">
            <BreadcrumbPage>{settingsSection.label}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    )
  }
  if (!selected) return null
  const [, section, detail] = selected
  const title =
    detail === 'follow-up'
      ? (followUp.data?.report.title ?? 'Follow-up')
      : problemId
        ? (problem.data?.title ?? 'Problem')
        : detail
  const isDetail = Boolean(
    problemId ||
    (followUpId && detail === 'follow-up') ||
    detail === 'New report',
  )
  return (
    <Breadcrumb aria-label="Breadcrumb">
      <BreadcrumbList className="min-w-0 flex-nowrap overflow-hidden">
        <BreadcrumbItem className="shrink-0">
          {isDetail ? (
            <BreadcrumbLink asChild>
              <Link
                to={
                  section === 'Problems'
                    ? '/problems'
                    : section === 'Inbox'
                      ? '/inbox'
                      : '/follow-ups'
                }
              >
                {section}
              </Link>
            </BreadcrumbLink>
          ) : (
            <BreadcrumbPage>{section}</BreadcrumbPage>
          )}
        </BreadcrumbItem>
        {isDetail ? (
          <>
            <BreadcrumbSeparator />
            <BreadcrumbItem className="min-w-0">
              <BreadcrumbPage className="block max-w-[min(45vw,28rem)] truncate">
                {title}
              </BreadcrumbPage>
            </BreadcrumbItem>
          </>
        ) : null}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
