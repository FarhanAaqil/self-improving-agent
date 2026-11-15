import { expect, test } from '@playwright/test'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

// The server writes each email to MAIL_OUTBOX_DIR (development only), so this test can
// follow the real verification link a new user would click.
const OUTBOX = process.env.MAIL_OUTBOX_DIR

async function linkMailedTo(email: string, path: string): Promise<string> {
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

test('a stranger signs up, confirms their email and makes an API key', async ({ page }) => {
  test.skip(!OUTBOX, 'set MAIL_OUTBOX_DIR for the server and the tests')
  const email = `e2e-${Date.now()}@example.com`
  const password = 'a long enough password'

  await page.goto('/signup')
  await page.getByLabel('email').fill(email)
  await page.getByLabel(/password/).fill(password)
  await page.getByRole('button', { name: 'create account' }).click()
  await expect(page.getByRole('heading', { name: 'One more step' })).toBeVisible()

  await page.goto(await linkMailedTo(email, '/verify'))
  await expect(page).toHaveURL(/\/\?welcome=1$/)
  await expect(page.getByRole('link', { name: email })).toBeVisible()

  await page.goto('/settings')
  await page.getByPlaceholder(/name it/).fill('e2e script')
  await page.getByRole('button', { name: 'create key' }).click()
  await expect(page.getByTestId('new-api-key')).toHaveText(/^sia_/)
  await expect(page.getByText('e2e script')).toBeVisible()

  // A new account starts on Free, with its limits in Settings and on the pricing page
  await expect(page.getByText('runs today')).toBeVisible()
  await page.goto('/pricing')
  await expect(page.getByText('your plan')).toBeVisible()

  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login/)

  await page.getByLabel('email').fill(email)
  await page.getByLabel('password').fill(password)
  await page.getByRole('button', { name: 'log in' }).click()
  await expect(page.getByRole('link', { name: email })).toBeVisible()
})
