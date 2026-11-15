import { TriangleAlert } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import BrandLogo from '../components/BrandLogo'

interface Doc {
  title: string
  sections: { heading: string; body: string[] }[]
}

// DRAFTS. Written to describe what this software actually does, as a starting point for a
// lawyer. They are not legal advice and must be reviewed before anyone relies on them.
const DOCS: Record<string, Doc> = {
  terms: {
    title: 'Terms of Service',
    sections: [
      { heading: 'The service', body: ['CODE_AGENT generates Python code from task descriptions, writes tests for it and runs both in an isolated sandbox. Results are produced by AI models and can be wrong even when marked "verified": a verified run means the code passed the tests that were written for it, nothing more. Review any code before you use it.'] },
      { heading: 'Your account', body: ['You need a valid email address and must keep your password and API keys secret. You are responsible for activity under your account. You must be old enough to form a binding contract where you live.'] },
      { heading: 'Your content', body: ['You keep the rights to the task descriptions you submit and the code produced for you. You give us permission to store and process them to provide the service. Do not submit content you have no right to share, or secrets such as passwords or private keys.'] },
      { heading: 'Groq keys and plans', body: ['Free accounts run on your own Groq API key, which stays in your browser and is sent only with your runs; your use of Groq is governed by Groq’s own terms. Paid plans may use our key within the published limits. Plans, limits and prices are described on the pricing page and may change with notice.', 'A paid plan stays active until the end of the period you paid for and then returns to Free.'] },
      { heading: 'Acceptable use', body: ['You must follow the Acceptable Use Policy. We may suspend or close accounts that break it or that put the service or other users at risk.'] },
      { heading: 'No warranty, limited liability', body: ['The service is provided "as is", without warranties of any kind. To the extent the law allows, we are not liable for indirect or consequential losses, or for losses caused by code the service produced.'] },
      { heading: 'Ending', body: ['You can delete your account at any time from Settings, which removes your runs, memories, keys and sessions. We may end the service with reasonable notice.'] },
    ],
  },
  privacy: {
    title: 'Privacy Policy',
    sections: [
      { heading: 'What we store', body: ['Your email address and a password hash (argon2; we never see or store your password itself). Your runs: task descriptions, generated code and tests, sandbox output, timings and token counts. Memories the agent keeps from your failed and repaired runs, used only for your own future runs. Your API keys as one-way hashes, plus their names and when they were used. Session records (hashed) while you are signed in.'] },
      { heading: 'What we never store', body: ['Your Groq API key: it lives in your browser tab and is sent only with each run. Card or payment details: payments go through the payment provider’s own checkout.'] },
      { heading: 'How it is used', body: ['To run the service for you, to enforce plan limits and prevent abuse, and to email you about your account (confirmations and password resets). We do not sell your data or use it for advertising.'] },
      { heading: 'Who else sees it', body: ['The model provider (Groq) receives your task and related prompts when a run uses a model. The email provider receives your address to deliver account emails. If error tracking is enabled, crash reports go to the error-tracking provider with your account id only, never request bodies, keys, cookies or code. A run you choose to share is visible to anyone with its link until you revoke it.'] },
      { heading: 'Keeping and deleting', body: ['Runs are kept for the history period of your plan and then deleted. Backups of the database are kept for a limited time (typically two weeks). Settings lets you export all of your data or delete your account; deletion removes your runs, memories, keys and sessions right away, and they age out of backups.'] },
      { heading: 'Contact', body: ['Questions about your data: contact the operator of this service.'] },
    ],
  },
  'acceptable-use': {
    title: 'Acceptable Use Policy',
    sections: [
      { heading: 'Do not', body: [
        'Try to break out of the sandbox, attack its host, or probe other users’ data (the built-in "Try to break it" demonstrations are the exception).',
        'Generate or run malware, credential stealers, spam tools, or code meant to attack systems you do not own.',
        'Create accounts in bulk, share accounts, or work around rate limits, plan limits or bans.',
        'Submit content that is illegal, or that infringes someone else’s rights.',
        'Overload the service, for example with automated traffic beyond your plan’s limits.',
      ] },
      { heading: 'Security research', body: ['Found a vulnerability? Report it to the operator privately and give a reasonable time to fix it before disclosing it.'] },
      { heading: 'Enforcement', body: ['Accounts that break this policy can be limited, disabled or deleted, with or without notice depending on the severity.'] },
    ],
  },
}

export default function Legal() {
  const { pathname } = useLocation()
  const slug = pathname.replace(/^\//, '')
  const doc = DOCS[slug]

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link to="/welcome" aria-label="CODE_AGENT home"><BrandLogo variant="full" size="sm" /></Link>
          <nav className="flex gap-3 text-xs text-ink-secondary" aria-label="Legal">
            <Link to="/terms" className="hover:text-ink">terms</Link>
            <Link to="/privacy" className="hover:text-ink">privacy</Link>
            <Link to="/acceptable-use" className="hover:text-ink">acceptable use</Link>
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-3xl space-y-6 px-4 py-10">
        <div role="note" className="flex gap-2 border border-status-warning/40 bg-status-warning-subtle p-3 text-sm text-status-warning">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <p><strong>DRAFT: needs human review.</strong> This text is a starting point, not legal advice, and is not yet in force.</p>
        </div>
        {doc ? (
          <article className="space-y-6">
            <h1 className="font-mono text-2xl font-bold">{doc.title}</h1>
            {doc.sections.map((section) => (
              <section key={section.heading}>
                <h2 className="font-mono text-base font-bold">{section.heading}</h2>
                {section.body.length > 1 && slug === 'acceptable-use' && section.heading === 'Do not' ? (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-secondary">
                    {section.body.map((line) => <li key={line}>{line}</li>)}
                  </ul>
                ) : (
                  section.body.map((p) => <p key={p} className="mt-2 text-sm leading-6 text-ink-secondary">{p}</p>)
                )}
              </section>
            ))}
          </article>
        ) : (
          <p>Not found.</p>
        )}
      </main>
    </div>
  )
}
