// Unit tests for the pure UI logic. Runs on Node's built-in runner (Node 24 strips types natively):
//   npm test
import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { diffLines, diffStats } from '../src/lib/diff.ts'
import { tokenize, tokenizeLines } from '../src/lib/highlight.ts'
import { deriveStages, narrate } from '../src/lib/narrate.ts'
import { createSseParser, type SseMessage } from '../src/lib/sse.ts'

describe('sse parser', () => {
  test('parses events split across arbitrary chunks', () => {
    const got: SseMessage[] = []
    const parser = createSseParser((m) => got.push(m))
    parser.feed('id: 1\nevent: run_started\nda')
    parser.feed('ta: {"a":1}\n\n: keep-alive\n\nid: 2\r\nevent: verified\r\ndata: {}\r\n\r\n')
    assert.deepEqual(got, [
      { id: 1, event: 'run_started', data: '{"a":1}' },
      { id: 2, event: 'verified', data: '{}' },
    ])
  })

  test('joins multi-line data and ignores comments', () => {
    const got: SseMessage[] = []
    createSseParser((m) => got.push(m)).feed(': hello\ndata: a\ndata: b\n\n')
    assert.equal(got[0].data, 'a\nb')
    assert.equal(got[0].id, null)
  })
})

describe('diff', () => {
  test('finds a minimal line diff', () => {
    const lines = diffLines('a\nb\nc', 'a\nx\nc\nd')
    assert.deepEqual(lines.map((l) => `${l.kind}:${l.text}`), ['same:a', 'remove:b', 'add:x', 'same:c', 'add:d'])
    assert.deepEqual(diffStats(lines), { added: 2, removed: 1 })
  })

  test('identical text has no changes', () => {
    assert.deepEqual(diffStats(diffLines('x\ny', 'x\ny')), { added: 0, removed: 0 })
  })
})

describe('highlight', () => {
  test('classifies python tokens', () => {
    const types = Object.fromEntries(
      tokenize('def add(a, b):  # sum\n    return len("x") + 1').filter((t) => t.type !== 'plain').map((t) => [t.text, t.type]),
    )
    assert.equal(types.def, 'keyword')
    assert.equal(types.add, 'def')
    assert.equal(types.len, 'builtin')
    assert.equal(types['"x"'], 'string')
    assert.equal(types['# sum'], 'comment')
    assert.equal(types['1'], 'number')
  })

  test('keeps strings intact across lines and reconstructs the source', () => {
    const code = 'x = """one\ntwo"""\ny = 2'
    const lines = tokenizeLines(code)
    assert.equal(lines.length, 3)
    assert.equal(lines.map((l) => l.map((t) => t.text).join('')).join('\n'), code)
    assert.equal(lines[1][0].type, 'string')
  })
})

describe('narration', () => {
  const ev = (event_id: number, type: string, payload: Record<string, unknown> = {}) => ({ event_id, type, payload })

  test('speaks in first person about memory and failures', () => {
    assert.match(narrate(ev(1, 'memory_recalled', { memories: [{}, {}] }))!.text, /seen 2 similar tasks/)
    const fail = narrate(ev(2, 'sandbox_result', { success: false, passed: 3, total: 5, failures: [{ test: 'test_empty', error: 'IndexError' }] }))!
    assert.equal(fail.mood, 'failure')
    assert.equal(fail.text, '3 of 5 tests passed.')
    assert.match(fail.detail ?? '', /test_empty/)
    assert.equal(narrate(ev(3, 'unknown_event')), null)
  })

  test('stepper reflects a repaired, verified run', () => {
    const events = [
      ev(1, 'run_started'), ev(2, 'memory_recalled', { memories: [] }), ev(3, 'tests_writing'),
      ev(4, 'tests_ready', { count: 4 }), ev(5, 'attempt_started', { attempt: 1 }), ev(6, 'code_generated', { attempt: 1, code: 'x' }),
      ev(7, 'sandbox_result', { attempt: 1, success: false }), ev(8, 'attempt_started', { attempt: 2 }),
      ev(9, 'code_generated', { attempt: 2, code: 'y' }), ev(10, 'sandbox_result', { attempt: 2, success: true }),
      ev(11, 'verified', { attempt: 2 }), ev(12, 'quality', { score: 0.9 }), ev(13, 'run_finished', { status: 'success' }),
    ]
    const stages = Object.fromEntries(deriveStages(events).map((s) => [s.id, s.state]))
    assert.deepEqual(stages, { recall: 'passed', spec: 'passed', generate: 'passed', verify: 'passed', repair: 'passed', review: 'passed' })
  })

  test('stepper marks a failed run without repairs needed as failed verification', () => {
    const events = [ev(1, 'run_started'), ev(2, 'tests_ready', { count: 0 }), ev(3, 'error', {}), ev(4, 'run_finished', { status: 'failed' })]
    const stages = Object.fromEntries(deriveStages(events).map((s) => [s.id, s.state]))
    assert.equal(stages.verify, 'failed')
    assert.equal(stages.spec, 'skipped')
  })
})
