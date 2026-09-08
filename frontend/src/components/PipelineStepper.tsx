import { CheckCircle2, Circle, FileText, Loader2, PlayCircle, ShieldCheck, TestTube2, XCircle, Zap } from 'lucide-react'

export type StepState = 'pending' | 'active' | 'passed' | 'failed' | 'skipped'

export interface PipelineStep {
  id: string
  name: string
  label: string
  state: StepState
  summary?: string
}

interface PipelineStepperProps {
  steps: PipelineStep[]
  className?: string
}

const STEP_ICONS: Record<string, React.ElementType> = {
  generate: PlayCircle,
  critique: CheckCircle2,
  test: TestTube2,
  performance: Zap,
  security: ShieldCheck,
  docs: FileText,
}

export default function PipelineStepper({ steps, className = '' }: PipelineStepperProps) {
  return (
    <div className={`bg-surface border border-border p-4 rounded ${className}`}>
      <div className="flex items-center justify-between overflow-x-auto pb-1 gap-2 sm:gap-4 select-none">
        {steps.map((step, idx) => {
          const StepIcon = STEP_ICONS[step.id] || Circle

          // State-based styling
          const isPassed = step.state === 'passed'
          const isFailed = step.state === 'failed'
          const isActive = step.state === 'active'
          const isSkipped = step.state === 'skipped'
          const isPending = step.state === 'pending'

          let textColor = 'text-ink-secondary'
          let iconColor = 'text-ink-tertiary'
          let stateIcon = <Circle className="h-3 w-3 text-ink-tertiary" />

          if (isPassed) {
            textColor = 'text-status-success'
            iconColor = 'text-status-success'
            stateIcon = <CheckCircle2 className="h-3.5 w-3.5 text-status-success" />
          } else if (isFailed) {
            textColor = 'text-status-danger'
            iconColor = 'text-status-danger'
            stateIcon = <XCircle className="h-3.5 w-3.5 text-status-danger" />
          } else if (isActive) {
            textColor = 'text-accent font-semibold'
            iconColor = 'text-accent'
            stateIcon = <Loader2 className="h-3.5 w-3.5 text-accent animate-spin" />
          } else if (isSkipped) {
            textColor = 'text-ink-tertiary line-through'
            iconColor = 'text-ink-tertiary'
          }

          return (
            <div key={step.id} className="flex-1 min-w-[120px] relative pb-2 group">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[11px] font-mono text-ink-tertiary">0{idx + 1}</span>
                <div className="flex items-center gap-1.5">
                  <StepIcon className={`h-3.5 w-3.5 ${iconColor}`} />
                  <span className={`text-xs font-medium ${textColor}`}>{step.name}</span>
                </div>
              </div>

              <div className="flex items-center gap-1 text-[11px] text-ink-secondary">
                {stateIcon}
                <span className="capitalize">{step.state}</span>
              </div>

              {/* Active step pulsing underline (the one deliberate motion moment) */}
              {isActive && (
                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent animate-pulse-underline rounded" />
              )}
              {isPassed && (
                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-status-success rounded opacity-70" />
              )}
              {isFailed && (
                <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-status-danger rounded" />
              )}
              {isPending && (
                <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-border rounded" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
