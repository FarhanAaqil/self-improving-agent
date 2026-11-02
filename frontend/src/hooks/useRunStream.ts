import { useEffect, useRef, useState } from 'react'
import { streamRunEvents } from '../api/client'
import type { RunEvent } from '../api/types'

export interface RunStream {
  events: RunEvent[]
  finished: boolean
  finalStatus: string | null
  connected: boolean
  error: string | null
}

const MAX_RETRIES = 6

/**
 * Follow a run live. Replays history first, then streams new events. If the
 * connection drops before `run_finished`, it reconnects with Last-Event-ID so
 * nothing is lost or duplicated.
 */
export function useRunStream(runId: string | undefined): RunStream {
  const [state, setState] = useState<RunStream>({
    events: [],
    finished: false,
    finalStatus: null,
    connected: false,
    error: null,
  })
  const lastId = useRef(0)

  useEffect(() => {
    if (!runId) return
    const controller = new AbortController()
    lastId.current = 0
    let finished = false
    let retries = 0

    // Reset for the new run; deferred so the effect body never sets state synchronously
    queueMicrotask(() => setState({ events: [], finished: false, finalStatus: null, connected: false, error: null }))

    const onEvent = (event: RunEvent) => {
      if (event.event_id <= lastId.current) return
      lastId.current = event.event_id
      retries = 0
      if (event.type === 'run_finished') finished = true
      setState((s) => ({
        ...s,
        connected: true,
        error: null,
        events: [...s.events, event],
        finished: s.finished || event.type === 'run_finished',
        finalStatus: event.type === 'run_finished' ? String(event.payload.status ?? '') : s.finalStatus,
      }))
    }

    const connect = async () => {
      while (!finished && !controller.signal.aborted && retries <= MAX_RETRIES) {
        try {
          setState((s) => ({ ...s, connected: true }))
          await streamRunEvents(runId, onEvent, { signal: controller.signal, lastEventId: lastId.current })
        } catch (err) {
          if (controller.signal.aborted) return
          retries++
          setState((s) => ({ ...s, connected: false, error: err instanceof Error ? err.message : 'Connection lost' }))
        }
        if (!finished && !controller.signal.aborted) {
          await new Promise((r) => setTimeout(r, Math.min(8000, 500 * 2 ** retries)))
        }
      }
      setState((s) => ({ ...s, connected: false }))
    }

    connect()
    return () => controller.abort()
  }, [runId])

  return state
}
