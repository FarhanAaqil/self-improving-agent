import { expect, type Page } from '@playwright/test'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

// The server writes each email to MAIL_OUTBOX_DIR (development only), so tests can
// follow the real verification link a new user would click.
export const OUTBOX = process.env.MAIL_OUTBOX_DIR

export async function linkMailedTo(email: string, path: string): Promise<string> {
  for (let i = 0; i < 40; i++) {
    // The folder appears with the first email, which is sent in the background
    const names = (() => { try { return readdirSync(OUTBOX!) } catch { return [] } })()
    for (const name of names.sort().reverse()) {
      const mail = JSON.parse(readFileSync(join(OUTBOX!, name), 'utf-8'))
      const match = mail.to === email && mail.body.match(new RegExp(`${path}\\?token=[\\w-]+`))
      if (match) return match[0]
    }
    await new Promise((r) => setTimeout(r, 250))
  }
  throw new Error(`no ${path} email for ${email}`)
}

/** Sign up a brand-new account through the UI and follow the emailed link. */
export async function signUp(page: Page, password = 'a long enough password'): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`
  await page.goto('/signup')
  await page.getByLabel('email').fill(email)
  await page.getByLabel(/password/).fill(password)
  await page.getByRole('button', { name: 'create account' }).click()
  await expect(page.getByRole('heading', { name: 'One more step' })).toBeVisible()
  await page.goto(await linkMailedTo(email, '/verify'))
  await expect(page).toHaveURL(/\/\?welcome=1$/)
  return email
}
