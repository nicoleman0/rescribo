import {
  CircleCheck,
  CircleMinus,
  Info,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { markProblemReviewed, type ProblemDetail } from '@/api/problems'
import {
  toneSurfaceClasses,
  type StatusTone,
} from '@/components/status/status-tone'
import { ActionError } from '@/components/states/action-error'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { problemStateTones } from './problem-format'
import { useProblemMutation } from './use-problem-mutation'

type Step = {
  tone: StatusTone
  heading: string
  body: string
  followUps?: boolean
  issue?: boolean
  review?: boolean
}

const toneIcons: Record<StatusTone, LucideIcon> = {
  neutral: CircleMinus,
  info: Info,
  progress: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: TriangleAlert,
}

function nextStep(problem: ProblemDetail): Step {
  const fixed = problem.state === 'fix_available'
  if (problem.state === 'not_planned') {
    return {
      tone: 'neutral',
      heading: 'Not planned',
      body: 'No fix is planned, so no follow-ups are prepared.',
      review: problem.needs_review,
    }
  }
  // The API does not say why the flag was set, so name every cause.
  if (problem.needs_review) {
    return {
      tone: 'warning',
      heading: 'Review the fix',
      body: `The GitHub issue closed or reopened, or a customer said they are still affected, after the last review. ${
        fixed
          ? 'Check the follow-up outcomes and the GitHub issue, then mark the problem reviewed.'
          : 'Check the GitHub issue, then confirm the fix under Fix or mark the problem reviewed.'
      }`,
      followUps: true,
      issue: true,
      review: true,
    }
  }
  if (fixed) {
    return {
      tone: 'success',
      heading: `Fix available in ${problem.fix_version}`,
      body: 'Follow-ups are prepared for the linked reports. Approve them in Follow-ups. A report linked later needs Confirm fix applies first.',
      followUps: true,
    }
  }
  return {
    tone: problemStateTones[problem.state],
    heading: 'Confirm the fix when it ships',
    body: 'Record the fix under Fix once customers can use it. Rescribo then prepares a follow-up for each linked report. Nothing is sent until a member approves it.',
  }
}

/** What a member does next on this problem, from its state and review flag. */
export function ProblemNextStep({
  workspaceId,
  problem,
}: {
  workspaceId: string
  problem: ProblemDetail
}) {
  const step = nextStep(problem)
  const Icon = toneIcons[step.tone]
  const issue = step.issue ? problem.engineering_issue : null
  const heading = useRef<HTMLHeadingElement>(null)
  // The button that had focus is gone once the flag clears.
  const review = useProblemMutation(
    workspaceId,
    () =>
      markProblemReviewed(workspaceId, problem.id, {
        expected_version: problem.version,
      }),
    () => heading.current?.focus(),
  )
  return (
    <div
      data-tone={step.tone}
      className={cn(
        'flex gap-3 rounded-card p-4',
        toneSurfaceClasses[step.tone],
      )}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="grid min-w-0 gap-1">
        <h2
          ref={heading}
          tabIndex={-1}
          className="font-semibold focus-visible:outline-2 focus-visible:outline-ring"
        >
          {step.heading}
        </h2>
        <p className="text-sm text-foreground">{step.body}</p>
        {step.followUps || issue || step.review ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {step.followUps ? (
              <Button
                asChild
                variant="outline"
                size="sm"
                className="text-foreground"
              >
                <Link to="/follow-ups">Open follow-ups</Link>
              </Button>
            ) : null}
            {issue ? (
              <Button
                asChild
                variant="outline"
                size="sm"
                className="text-foreground"
              >
                <a href={issue.url} target="_blank" rel="noreferrer">
                  Open GitHub issue #{issue.number}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </Button>
            ) : null}
            {step.review ? (
              <Button
                variant="outline"
                size="sm"
                className="text-foreground"
                disabled={review.isPending}
                onClick={() => review.mutate(undefined)}
              >
                {review.isPending ? 'Marking reviewed…' : 'Mark reviewed'}
              </Button>
            ) : null}
          </div>
        ) : null}
        {review.error ? (
          <ActionError
            error={review.error}
            title="The problem was not marked reviewed"
            record="problem"
          />
        ) : null}
      </div>
    </div>
  )
}
