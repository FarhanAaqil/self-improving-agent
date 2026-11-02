// Small Python tokenizer for read-only code views. It returns plain tokens that the
// CodeBlock renders as React spans, so no HTML string is ever injected.

export type TokenType = 'keyword' | 'string' | 'comment' | 'number' | 'builtin' | 'def' | 'decorator' | 'plain'

export interface Token {
  type: TokenType
  text: string
}

const KEYWORDS = new Set([
  'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
  'def', 'del', 'elif', 'else', 'except', 'finally', 'for', 'from', 'global', 'if', 'import',
  'in', 'is', 'lambda', 'match', 'case', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
  'try', 'while', 'with', 'yield',
])

const BUILTINS = new Set([
  'abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'filter', 'float', 'int', 'isinstance', 'len',
  'list', 'map', 'max', 'min', 'object', 'print', 'range', 'reversed', 'round', 'self', 'set',
  'sorted', 'str', 'sum', 'super', 'tuple', 'type', 'zip', 'Exception', 'ValueError', 'TypeError',
  'KeyError', 'IndexError', 'RuntimeError',
])

// Order matters: comments and strings first so their contents aren't tokenized.
const PATTERN = new RegExp(
  [
    String.raw`(#[^\n]*)`, // 1 comment
    String.raw`([rbuf]{0,2}"""[\s\S]*?(?:"""|$)|[rbuf]{0,2}'''[\s\S]*?(?:'''|$))`, // 2 triple string
    String.raw`([rbuf]{0,2}"(?:\\.|[^"\\\n])*"?|[rbuf]{0,2}'(?:\\.|[^'\\\n])*'?)`, // 3 string
    String.raw`(@[A-Za-z_][\w.]*)`, // 4 decorator
    String.raw`(\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?j?\b|\b0[xob][\da-fA-F_]+\b)`, // 5 number
    String.raw`([A-Za-z_]\w*)`, // 6 identifier
  ].join('|'),
  'gi',
)

export function tokenize(code: string): Token[] {
  const tokens: Token[] = []
  let last = 0
  let previousWord = ''
  PATTERN.lastIndex = 0
  for (let m = PATTERN.exec(code); m; m = PATTERN.exec(code)) {
    if (m.index > last) tokens.push({ type: 'plain', text: code.slice(last, m.index) })
    const [text, comment, triple, str, deco, num, ident] = m
    let type: TokenType = 'plain'
    if (comment) type = 'comment'
    else if (triple || str) type = 'string'
    else if (deco) type = 'decorator'
    else if (num) type = 'number'
    else if (ident) {
      if (KEYWORDS.has(ident)) type = 'keyword'
      else if (previousWord === 'def' || previousWord === 'class') type = 'def'
      else if (BUILTINS.has(ident)) type = 'builtin'
    }
    if (ident) previousWord = ident
    tokens.push({ type, text })
    last = m.index + text.length
    if (text.length === 0) PATTERN.lastIndex++
  }
  if (last < code.length) tokens.push({ type: 'plain', text: code.slice(last) })
  return tokens
}

// Split tokens into lines so code views can number them.
export function tokenizeLines(code: string): Token[][] {
  const lines: Token[][] = [[]]
  for (const token of tokenize(code)) {
    const parts = token.text.split('\n')
    parts.forEach((part, index) => {
      if (index > 0) lines.push([])
      if (part) lines[lines.length - 1].push({ type: token.type, text: part })
    })
  }
  return lines
}
