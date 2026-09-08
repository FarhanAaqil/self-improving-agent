import { Check, X } from 'lucide-react'

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

function ViewfinderReticle({
  index,
  state,
}: {
  index: number
  state: StepState
}) {
  const isPassed = state === 'passed'
  const isFailed = state === 'failed'
  const isActive = state === 'active'

  let bracketColor = 'border-border-strong text-ink-tertiary'
  if (isActive) bracketColor = 'border-accent text-accent animate-bracket-breathe'
  else if (isPassed) bracketColor = 'border-status-success text-status-success'
  else if (isFailed) bracketColor = 'border-status-danger text-status-danger'

  return (
    <div
      className={`relative w-9 h-9 flex items-center justify-center font-mono text-xs select-none transition-all ${bracketColor}`}
    >
      {/* Top Left Bracket */}
      <span className="absolute top-0 left-0 w-2.5 h-2.5 border-t-2 border-l-2 border-current pointer-events-none" />
      {/* Top Right Bracket */}
      <span className="absolute top-0 right-0 w-2.5 h-2.5 border-t-2 border-r-2 border-current pointer-events-none" />
      {/* Bottom Left Bracket */}
      <span className="absolute bottom-0 left-0 w-2.5 h-2.5 border-b-2 border-l-2 border-current pointer-events-none" />
      {/* Bottom Right Bracket */}
      <span className="absolute bottom-0 right-0 w-2.5 h-2.5 border-b-2 border-r-2 border-current pointer-events-none" />

      {/* Center Indicator */}
      {isPassed ? (
        <Check className="h-4 w-4 text-status-success stroke-[2.5]" />
      ) : isFailed ? (
        <X className="h-4 w-4 text-status-danger stroke-[2.5]" />
      ) : (
        <span className={`font-mono text-xs ${isActive ? 'font-bold text-accent' : 'font-normal text-ink-tertiary'}`}>
          0{index + 1}
        </span>
      )}
    </div>
  )
}

export default function PipelineStepper({ steps, className = '' }: PipelineStepperProps) {
  return (
    <div className={`bg-surface border border-border p-5 select-none ${className}`}>
      <div className="flex items-center justify-between overflow-x-auto pb-1 gap-2">
        {steps.map((step, idx) => {
          const isLast = idx === steps.length - 1
          const isActive = step.state === 'active'
          const isPassed = step.state === 'passed'
          const isFailed = step.state === 'failed'

          let nameColor = 'text-ink-secondary'
          if (isActive) nameColor = 'text-accent font-bold'
          else if (isPassed) nameColor = 'text-status-success font-semibold'
          else if (isFailed) nameColor = 'text-status-danger font-semibold'

          return (
            <div key={step.id} className="flex-1 flex items-center min-w-[110px]">
              <div className="flex flex-col items-center flex-1">
                {/* Viewfinder reticle square */}
                <ViewfinderReticle index={idx} state={step.state} />

                {/* Monospace Stage Identifier */}
                <div className="mt-2.5 text-center">
                  <div className={`text-xs font-mono leading-tight tracking-tight ${nameColor}`}>
                    {step.name}
                  </div>
                  <div className="text-[10px] font-mono text-ink-tertiary mt-0.5 uppercase tracking-wider">
                    {step.state}
                  </div>
                </div>
              </div>

              {/* Thin connecting rule between stages */}
              {!isLast && (
                <div className="w-6 sm:w-10 h-[1px] bg-border mx-1 -mt-8 self-center" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
