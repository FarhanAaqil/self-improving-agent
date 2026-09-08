import { useState } from 'react'
import { GitCompare, Minus, Plus } from 'lucide-react'
import type { AttemptOut } from '../api/types'

interface CodeDiffViewProps {
  attempts: AttemptOut[]
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged'
  text: string
  oldLineNum?: number
  newLineNum?: number
}

function computeSimpleDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')
  const result: DiffLine[] = []

  let oldIdx = 0
  let newIdx = 0

  while (oldIdx < oldLines.length || newIdx < newLines.length) {
    if (oldIdx < oldLines.length && newIdx < newLines.length) {
      if (oldLines[oldIdx] === newLines[newIdx]) {
        result.push({
          type: 'unchanged',
          text: oldLines[oldIdx],
          oldLineNum: oldIdx + 1,
          newLineNum: newIdx + 1,
        })
        oldIdx++
        newIdx++
      } else {
        const foundInNew = newLines.slice(newIdx, newIdx + 4).indexOf(oldLines[oldIdx])
        if (foundInNew !== -1) {
          for (let i = 0; i < foundInNew; i++) {
            result.push({
              type: 'added',
              text: newLines[newIdx],
              newLineNum: newIdx + 1,
            })
            newIdx++
          }
        } else {
          result.push({
            type: 'removed',
            text: oldLines[oldIdx],
            oldLineNum: oldIdx + 1,
          })
          oldIdx++
        }
      }
    } else if (oldIdx < oldLines.length) {
      result.push({
        type: 'removed',
        text: oldLines[oldIdx],
        oldLineNum: oldIdx + 1,
      })
      oldIdx++
    } else {
      result.push({
        type: 'added',
        text: newLines[newIdx],
        newLineNum: newIdx + 1,
      })
      newIdx++
    }
  }

  return result
}

export default function CodeDiffView({ attempts }: CodeDiffViewProps) {
  if (attempts.length < 2) {
    return null
  }

  const [fromAttemptNum, setFromAttemptNum] = useState<number>(attempts[0].attempt_number)
  const [toAttemptNum, setToAttemptNum] = useState<number>(
    attempts[attempts.length - 1].attempt_number
  )

  const fromAttempt = attempts.find((a) => a.attempt_number === fromAttemptNum) || attempts[0]
  const toAttempt =
    attempts.find((a) => a.attempt_number === toAttemptNum) || attempts[attempts.length - 1]

  const diffLines = computeSimpleDiff(fromAttempt.generated_code, toAttempt.generated_code)

  const addedCount = diffLines.filter((l) => l.type === 'added').length
  const removedCount = diffLines.filter((l) => l.type === 'removed').length

  return (
    <div className="bg-surface border border-border overflow-hidden space-y-0 font-mono">
      {/* Diff Header */}
      <div className="px-4 py-3 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-sunken">
        <div className="flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-accent" />
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-ink">
            repair verification diff
          </h3>
          <span className="flex items-center gap-2 ml-2 text-xs font-mono">
            <span className="text-status-success flex items-center font-bold">
              <Plus className="h-3 w-3 inline" />
              {addedCount}
            </span>
            <span className="text-status-danger flex items-center font-bold">
              <Minus className="h-3 w-3 inline" />
              {removedCount}
            </span>
          </span>
        </div>

        {/* Compare selectors */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-ink-secondary">compare:</span>
          <select
            value={fromAttemptNum}
            onChange={(e) => setFromAttemptNum(Number(e.target.value))}
            className="bg-surface border border-border text-ink px-2 py-1 text-xs focus:outline-none"
          >
            {attempts.map((a) => (
              <option key={a.attempt_number} value={a.attempt_number}>
                attempt 0{a.attempt_number} ({a.success ? 'pass' : 'fail'})
              </option>
            ))}
          </select>
          <span className="text-ink-tertiary">→</span>
          <select
            value={toAttemptNum}
            onChange={(e) => setToAttemptNum(Number(e.target.value))}
            className="bg-surface border border-border text-ink px-2 py-1 text-xs focus:outline-none"
          >
            {attempts.map((a) => (
              <option key={a.attempt_number} value={a.attempt_number}>
                attempt 0{a.attempt_number} ({a.success ? 'pass' : 'fail'})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Diff Lines Table */}
      <div className="overflow-x-auto max-h-[440px] bg-surface font-mono text-xs">
        <table className="w-full border-collapse">
          <tbody>
            {diffLines.map((line, idx) => {
              const isAdded = line.type === 'added'
              const isRemoved = line.type === 'removed'

              return (
                <tr
                  key={idx}
                  className={`leading-relaxed ${
                    isAdded
                      ? 'bg-status-success-subtle text-status-success'
                      : isRemoved
                      ? 'bg-status-danger-subtle text-status-danger'
                      : 'text-ink hover:bg-surface-sunken'
                  }`}
                >
                  <td className="w-10 px-2 py-0.5 text-right select-none text-[11px] text-ink-tertiary border-r border-border">
                    {line.oldLineNum || ''}
                  </td>
                  <td className="w-10 px-2 py-0.5 text-right select-none text-[11px] text-ink-tertiary border-r border-border">
                    {line.newLineNum || ''}
                  </td>
                  <td className="w-6 px-1 py-0.5 text-center select-none font-bold">
                    {isAdded ? '+' : isRemoved ? '-' : ' '}
                  </td>
                  <td className="px-3 py-0.5 whitespace-pre overflow-x-auto font-mono">
                    {line.text || ' '}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
