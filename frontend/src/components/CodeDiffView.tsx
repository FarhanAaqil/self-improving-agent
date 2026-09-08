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
        // Lookahead check to see if current old line appears soon in newLines
        const foundInNew = newLines.slice(newIdx, newIdx + 4).indexOf(oldLines[oldIdx])
        if (foundInNew !== -1) {
          // Lines were added in new
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
    <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden shadow-sm space-y-0">
      {/* Diff Header */}
      <div className="px-5 py-4 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60">
        <div className="flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-100">Repair Code Diff</h3>
          <span className="flex items-center gap-2 ml-2 text-xs font-mono">
            <span className="text-emerald-400 flex items-center">
              <Plus className="h-3 w-3 inline" />
              {addedCount}
            </span>
            <span className="text-rose-400 flex items-center">
              <Minus className="h-3 w-3 inline" />
              {removedCount}
            </span>
          </span>
        </div>

        {/* Compare selectors */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">Comparing:</span>
          <select
            value={fromAttemptNum}
            onChange={(e) => setFromAttemptNum(Number(e.target.value))}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs"
          >
            {attempts.map((a) => (
              <option key={a.attempt_number} value={a.attempt_number}>
                Attempt #{a.attempt_number} ({a.success ? 'pass' : 'fail'})
              </option>
            ))}
          </select>
          <span className="text-slate-500">→</span>
          <select
            value={toAttemptNum}
            onChange={(e) => setToAttemptNum(Number(e.target.value))}
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs"
          >
            {attempts.map((a) => (
              <option key={a.attempt_number} value={a.attempt_number}>
                Attempt #{a.attempt_number} ({a.success ? 'pass' : 'fail'})
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Diff Lines Table */}
      <div className="overflow-x-auto max-h-[480px] bg-slate-950 font-mono text-xs">
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
                      ? 'bg-emerald-950/25 text-emerald-200'
                      : isRemoved
                        ? 'bg-rose-950/25 text-rose-200'
                        : 'text-slate-300 hover:bg-slate-900/40'
                  }`}
                >
                  <td className="w-10 px-2 py-0.5 text-right select-none text-[11px] text-slate-600 border-r border-slate-900">
                    {line.oldLineNum || ''}
                  </td>
                  <td className="w-10 px-2 py-0.5 text-right select-none text-[11px] text-slate-600 border-r border-slate-900">
                    {line.newLineNum || ''}
                  </td>
                  <td className="w-6 px-1 py-0.5 text-center select-none font-bold">
                    {isAdded ? '+' : isRemoved ? '-' : ' '}
                  </td>
                  <td className="px-3 py-0.5 whitespace-pre overflow-x-auto selection:bg-indigo-500/30">
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
