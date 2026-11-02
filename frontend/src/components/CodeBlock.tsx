import { Check, Copy } from 'lucide-react'
import { useMemo, useState } from 'react'
import { copyText } from '../lib/clipboard'
import { tokenizeLines } from '../lib/highlight'

interface CodeBlockProps {
  code: string
  maxHeight?: string
  /** 1-based line numbers to emphasise (e.g. lines changed since the last attempt) */
  highlight?: Set<number>
  label?: string
  streaming?: boolean
}

export function CopyButton({ text, label = 'copy' }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        if (await copyText(text)) {
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        }
      }}
      className="btn-ghost px-2 py-1 text-[10px]"
      aria-label={`Copy ${label}`}
    >
      {copied ? <Check className="h-3 w-3" aria-hidden /> : <Copy className="h-3 w-3" aria-hidden />}
      {copied ? 'copied' : label}
    </button>
  )
}

export default function CodeBlock({ code, maxHeight = '28rem', highlight, label, streaming }: CodeBlockProps) {
  const lines = useMemo(() => tokenizeLines(code), [code])
  const gutter = String(lines.length).length

  return (
    <div className="relative border border-border bg-surface-sunken">
      {label && (
        <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
          <span className="font-mono text-[11px] text-ink-muted">{label}</span>
          <CopyButton text={code} />
        </div>
      )}
      <pre className="overflow-auto py-2 font-mono text-[12.5px] leading-6" style={{ maxHeight }} tabIndex={0}>
        <code>
          {lines.map((tokens, index) => {
            const lineNo = index + 1
            const marked = highlight?.has(lineNo)
            return (
              <div
                key={index}
                className={`flex px-3 ${marked ? 'bg-accent/10 shadow-[inset_2px_0_0_rgb(var(--accent))]' : ''}`}
              >
                <span
                  className="mr-4 shrink-0 select-none text-right text-ink-tertiary"
                  style={{ width: `${gutter}ch` }}
                  aria-hidden
                >
                  {lineNo}
                </span>
                <span className="whitespace-pre">
                  {tokens.length === 0 ? ' ' : tokens.map((t, i) =>
                    t.type === 'plain' ? t.text : <span key={i} className={`tok-${t.type}`}>{t.text}</span>,
                  )}
                  {streaming && lineNo === lines.length && (
                    <span className="ml-0.5 inline-block h-4 w-2 translate-y-0.5 animate-caret bg-accent" aria-hidden />
                  )}
                </span>
              </div>
            )
          })}
        </code>
      </pre>
    </div>
  )
}
