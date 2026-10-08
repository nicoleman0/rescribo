import {
  CircleCheck,
  CircleMinus,
  Info,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import type { ProblemDetail } from '@/api/problems'
import type { StatusTone } from '@/components/status/status-tone'
import { touchTarget } from '@/components/layout/touch-target'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { problemStateTones } from './problem-format'

type Step = {
  tone: StatusTone
  heading: string
  body: string
  followUps?: boolean
  issue?: boolean
}

// Literal class strings so Tailwind can find them.
const toneClasses: Record<StatusTone, string> = {
  neutral: 'bg-tone-neutral text-tone-neutral-foreground',
  info: 'bg-tone-info text-tone-info-foreground',
  progress: 'bg-tone-progress text-tone-progress-foreground',
  success: 'bg-tone-success text-tone-success-foreground',
  warning: 'bg-tone-warning text-tone-warning-foreground',
  danger: 'bg-tone-danger text-tone-danger-foreground',
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
    }
  }
  // The API does not say why the flag was set, so name every cause.
  if (problem.needs_review) {
    return {
      tone: 'warning',
      heading: 'Review the fix',
      body: `The GitHub issue closed or reopened, or a customer said they are still affected, after the last review. ${
        fixed
          ? 'Check the follow-up outcomes and the GitHub issue.'
          : 'Check the GitHub issue, then confirm the fix under Fix.'
      }`,
      followUps: true,
      issue: true,
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
export function ProblemNextStep({ problem }: { problem: ProblemDetail }) {
  const step = nextStep(problem)
  const Icon = toneIcons[step.tone]
  const issue = step.issue ? problem.engineering_issue : null
  return (
    <div
      data-tone={step.tone}
      className={cn('flex gap-3 rounded-card p-4', toneClasses[step.tone])}
    >
      <Icon aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div className="grid min-w-0 gap-1">
        <h2 className="font-semibold">{step.heading}</h2>
        <p className="text-sm text-foreground">{step.body}</p>
        {step.followUps || issue ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {step.followUps ? (
              <Button
                asChild
                variant="outline"
                size="sm"
                className={cn('text-foreground', touchTarget)}
              >
                <Link to="/follow-ups">Open follow-ups</Link>
              </Button>
            ) : null}
            {issue ? (
              <Button
                asChild
                variant="outline"
                size="sm"
                className={cn('text-foreground', touchTarget)}
              >
                <a href={issue.url} target="_blank" rel="noreferrer">
                  Open GitHub issue #{issue.number}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
