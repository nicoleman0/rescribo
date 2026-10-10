import { ArrowLeft } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useWorkspace } from '@/components/auth/use-workspace'
import { cn } from '@/lib/utils'
import { FollowUpDetailContent } from './follow-up-detail'

export function FollowUpDetailPage() {
  const { workspace } = useWorkspace()
  const { followUpId = '' } = useParams()
  const [params] = useSearchParams()
  const search = params.toString()
  const backTo = `/follow-ups${search ? `?${search}` : ''}`

  return (
    <div className="animate-page-enter grid gap-6">
      <Button asChild variant="ghost" size="sm" className={cn('w-fit')}>
        <Link to={backTo}>
          <ArrowLeft aria-hidden="true" />
          Back to follow-ups
        </Link>
      </Button>
      <FollowUpDetailContent
        key={followUpId}
        workspaceId={workspace.id}
        followUpId={followUpId}
        layout="page"
      />
    </div>
  )
}
