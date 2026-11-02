// Line diff via longest common subsequence. Generated files are small (hundreds of
// lines), so the O(n*m) table is fine and gives a correct, minimal diff.

export type DiffKind = 'same' | 'add' | 'remove'

export interface DiffLine {
  kind: DiffKind
  text: string
  oldNo?: number
  newNo?: number
}

const MAX_CELLS = 400_000

export function diffLines(before: string, after: string): DiffLine[] {
  const a = before.split('\n')
  const b = after.split('\n')

  // Too large for a full table: fall back to "everything changed"
  if (a.length * b.length > MAX_CELLS) {
    return [
      ...a.map((text, i) => ({ kind: 'remove' as const, text, oldNo: i + 1 })),
      ...b.map((text, i) => ({ kind: 'add' as const, text, newNo: i + 1 })),
    ]
  }

  const rows = a.length + 1
  const cols = b.length + 1
  const lcs = new Uint32Array(rows * cols)
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i * cols + j] =
        a[i] === b[j]
          ? lcs[(i + 1) * cols + j + 1] + 1
          : Math.max(lcs[(i + 1) * cols + j], lcs[i * cols + j + 1])
    }
  }

  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: 'same', text: a[i], oldNo: i + 1, newNo: j + 1 })
      i++
      j++
    } else if (lcs[(i + 1) * cols + j] >= lcs[i * cols + j + 1]) {
      out.push({ kind: 'remove', text: a[i], oldNo: i + 1 })
      i++
    } else {
      out.push({ kind: 'add', text: b[j], newNo: j + 1 })
      j++
    }
  }
  while (i < a.length) out.push({ kind: 'remove', text: a[i], oldNo: ++i })
  while (j < b.length) out.push({ kind: 'add', text: b[j], newNo: ++j })
  return out
}

export function diffStats(lines: DiffLine[]) {
  return {
    added: lines.filter((l) => l.kind === 'add').length,
    removed: lines.filter((l) => l.kind === 'remove').length,
  }
}
