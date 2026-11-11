// Turns raw run events into the agent's own short, first-person story.
// Tone is the actual connection with the user: brief, honest, specific.

import type { RunEvent } from '../api/types'

export type Mood = 'thinking' | 'memory' | 'success' | 'failure' | 'neutral'

export interface StoryLine {
  id: number
  mood: Mood
  text: string
  detail?: string
  attempt?: number
}

type P = Record<string, unknown>

const num = (v: unknown) => (typeof v === 'number' ? v : 0)
const str = (v: unknown) => (typeof v === 'string' ? v : '')

export function narrate(event: RunEvent): StoryLine | null {
  const p = event.payload as P
  const base = { id: event.event_id, attempt: typeof p.attempt === 'number' ? p.attempt : undefined }
  switch (event.type) {
    case 'run_started':
      return { ...base, mood: 'neutral', text: `Got it. Working on this with ${str(p.model)}, up to ${num(p.max_attempts)} attempts.` }
    case 'memory_recalled': {
      const memories = Array.isArray(p.memories) ? p.memories : []
      return memories.length
        ? { ...base, mood: 'memory', text: `I've seen ${memories.length} similar task${memories.length > 1 ? 's' : ''} before. I'll avoid what went wrong.` }
        : { ...base, mood: 'memory', text: 'Nothing similar in my memory yet. Fresh start.' }
    }
    case 'tests_writing':
      return { ...base, mood: 'thinking', text: 'Writing spec tests from your description first…' }
    case 'tests_ready':
      return num(p.count)
        ? { ...base, mood: 'thinking', text: `Wrote ${num(p.count)} spec tests. The code has to pass every one.` }
        : { ...base, mood: 'neutral', text: 'No spec tests this time, so a clean run is the bar.' }
    case 'attempt_started':
      return num(p.attempt) > 1
        ? { ...base, mood: 'thinking', text: `Attempt ${num(p.attempt)}: rewriting with the fix in mind…` }
        : { ...base, mood: 'thinking', text: 'Attempt 1: writing the code…' }
    case 'code_generated':
      return { ...base, mood: 'neutral', text: `Code ready, ${str(p.code).split('\n').length} lines.` }
    case 'sandbox_started':
      return { ...base, mood: 'thinking', text: 'Running it in a locked container: no network, no root…' }
    case 'sandbox_result': {
      const total = num(p.total)
      if (p.success) {
        return { ...base, mood: 'success', text: total ? `All ${total} tests passed.` : 'Ran cleanly.' }
      }
      const failures = Array.isArray(p.failures) ? (p.failures as { test: string; error: string }[]) : []
      return {
        ...base,
        mood: 'failure',
        text: total ? `${num(p.passed)} of ${total} tests passed.` : 'It crashed.',
        detail: failures[0] ? `${failures[0].test}: ${failures[0].error}` : str(p.stderr).split('\n').slice(-1)[0],
      }
    }
    case 'diagnosing':
      return { ...base, mood: 'thinking', text: 'Working out why…' }
    case 'diagnosis':
      return { ...base, mood: 'failure', text: str(p.summary), detail: str(p.fix_plan) ? `Plan: ${str(p.fix_plan)}` : undefined }
    case 'tests_triaged': {
      const dropped = Array.isArray(p.dropped) ? p.dropped.length : 0
      return p.passed
        ? { ...base, mood: 'success', text: `${dropped} of my tests contradicted the task, so I removed ${dropped === 1 ? 'it' : 'them'}. The code passes the rest.`, detail: str(p.reason) }
        : { ...base, mood: 'neutral', text: 'I suspected some tests were wrong, but the code fails without them too.' }
    }
    case 'tests_rewritten':
      return { ...base, mood: 'thinking', text: 'The tests themselves looked wrong, so I rewrote them.', detail: str(p.reason) }
    case 'early_stop':
      return { ...base, mood: 'failure', text: "I'm stopping here; another try won't help.", detail: str(p.reason) }
    case 'mutation_tested': {
      if (!p.available || !num(p.total)) return null
      const total = num(p.total)
      const killed = num(p.killed)
      const survivors = Array.isArray(p.survivors) ? (p.survivors as { line: number; change: string }[]) : []
      if (p.stage === 'final') {
        return { ...base, mood: killed === total ? 'success' : 'neutral', text: `With the stricter tests, ${killed} of ${total} deliberate breaks get caught.` }
      }
      const ways = `${total} different way${total === 1 ? '' : 's'}`
      return killed === total
        ? { ...base, mood: 'success', text: `I broke my own code ${ways} and the tests caught ${total === 1 ? 'it' : 'every one'}.` }
        : {
            ...base,
            mood: 'thinking',
            text: `I broke my own code ${ways}; the tests missed ${total - killed}. Writing stricter tests…`,
            detail: survivors[0] ? `e.g. line ${survivors[0].line}: ${survivors[0].change} went unnoticed` : undefined,
          }
    }
    case 'tests_strengthened': {
      const added = num(p.added)
      if (p.outcome === 'kept') return { ...base, mood: 'success', text: `Added ${added} stricter test${added === 1 ? '' : 's'}. The code still passes.` }
      if (p.outcome === 'found_bug') return { ...base, mood: 'failure', text: 'The stricter tests caught a real bug the first tests missed. Fixing it.', detail: str(p.reason) }
      return { ...base, mood: 'neutral', text: 'The stricter tests I tried turned out to be wrong, so I dropped them.' }
    }
    case 'verified':
      return { ...base, mood: 'success', text: `Verified on attempt ${num(p.attempt)}.` }
    case 'static_analysis': {
      const issues = Array.isArray(p.bandit_issues) ? p.bandit_issues.length : 0
      return {
        ...base,
        mood: issues ? 'failure' : 'neutral',
        text: issues ? `Static scan flagged ${issues} security issue${issues > 1 ? 's' : ''}.` : 'Static security scan came back clean.',
        detail: p.complexity ? `Highest cyclomatic complexity: ${num(p.complexity)}` : undefined,
      }
    }
    case 'docs_verified':
      return p.kept
        ? { ...base, mood: 'success', text: 'Added docstrings and re-ran the tests. Still green.' }
        : { ...base, mood: 'neutral', text: 'The documented version broke something, so I kept the verified one.' }
    case 'quality':
      return typeof p.score === 'number'
        ? { ...base, mood: 'neutral', text: `Quality score: ${(p.score * 10).toFixed(1)} / 10.` }
        : null
    case 'run_finished': {
      const status = str(p.status)
      const text =
        status === 'success' ? 'Done. Everything below is verified.'
          : status === 'early_stopped' ? 'Stopped early. I saved what I learned for next time.'
            : status === 'max_retries_exceeded' ? 'Out of attempts. I saved this failure so I do better next time.'
              : 'The run ended with an error.'
      return { ...base, mood: status === 'success' ? 'success' : 'failure', text }
    }
    case 'error':
      return { ...base, mood: 'failure', text: str(p.message) || 'Something went wrong.' }
    default:
      return null
  }
}

// Coarse stage model for the stepper, derived from which events have arrived.
export type StageState = 'pending' | 'active' | 'passed' | 'failed' | 'skipped'

export interface Stage {
  id: string
  label: string
  hint: string
  state: StageState
}

export function deriveStages(events: RunEvent[], finishedStatus?: string): Stage[] {
  const has = (t: string) => events.some((e) => e.type === t)
  const last = events[events.length - 1]?.type
  const finished = has('run_finished') || Boolean(finishedStatus)
  const verified = has('verified')
  const attempts = events.filter((e) => e.type === 'attempt_started').length
  const failures = events.filter((e) => e.type === 'sandbox_result' && !(e.payload as P).success).length
  const testsSkipped = has('tests_ready') && !num((events.find((e) => e.type === 'tests_ready')?.payload as P)?.count)

  const state = (done: boolean, active: boolean, failed = false): StageState =>
    failed ? 'failed' : done ? 'passed' : active ? 'active' : 'pending'

  return [
    { id: 'recall', label: 'recall', hint: 'search memory', state: state(has('memory_recalled') || has('tests_writing') || attempts > 0, has('run_started') && !finished) },
    { id: 'spec', label: 'spec', hint: 'write tests first', state: testsSkipped ? 'skipped' : state(has('tests_ready'), has('tests_writing')) },
    { id: 'generate', label: 'generate', hint: `attempt ${Math.max(1, attempts)}`, state: state(has('code_generated') && (verified || finished), last === 'attempt_started' || last === 'tests_ready') },
    {
      id: 'verify',
      label: 'verify',
      hint: 'sandbox + tests',
      state: verified ? 'passed' : finished && !verified ? 'failed' : last === 'sandbox_started' ? 'active' : 'pending',
    },
    {
      id: 'repair',
      label: 'repair',
      hint: failures ? `${failures} fix${failures > 1 ? 'es' : ''}` : 'if needed',
      state: failures === 0 ? (verified || finished ? 'skipped' : 'pending') : verified ? 'passed' : finished ? 'failed' : 'active',
    },
    { id: 'review', label: 'review', hint: 'audit & document', state: state(has('quality'), verified && !has('quality')) },
  ]
}
