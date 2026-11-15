import { expect, test } from '@playwright/test'
import { OUTBOX, signUp } from './mail'

test('a visitor watches a live demo run on the landing page, no account needed', async ({ page }) => {
  await page.goto('/welcome')
  await expect(page.getByRole('heading', { name: /proves it works/ })).toBeVisible()
  await page.getByRole('button', { name: 'start the demo' }).click()

  await expect(page.getByText('I subtracted where the task asks for a sum.')).toBeVisible()
  await expect(page.getByText('Verified on attempt 2.')).toBeVisible()
  await expect(page.getByRole('img', { name: /Verified on attempt 2/ })).toBeVisible()

  // The result is a public share page that links back to the landing page
  await page.getByRole('link', { name: 'see the certificate' }).click()
  await expect(page.getByText('verification certificate')).toBeVisible()
  await expect(page.getByRole('link', { name: 'try it free' })).toHaveAttribute('href', /\/welcome/)
})

test('a new account: paste a key, run the starter task, watch it fail, fix itself and pass', async ({ page }) => {
  test.skip(!OUTBOX, 'set MAIL_OUTBOX_DIR for the server and the tests')
  const password = 'a long enough password'
  await signUp(page, password)

  // Free plans run on the user's own key: nothing runs until it's pasted
  await expect(page.getByRole('heading', { name: 'Add your Groq key to start' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'run it' })).toBeDisabled()
  await page.getByLabel('Your Groq API key').fill('gsk_e2e_not_a_real_key')
  await page.getByRole('button', { name: 'use this key' }).click()

  await expect(page.getByRole('heading', { name: /first verified run/ })).toBeVisible()
  await page.getByRole('button', { name: 'run the starter task' }).click()
  await expect(page).toHaveURL(/\/runs\/run_/)
  await expect(page.getByText(/Attempt 2/).first()).toBeVisible()
  await expect(page.getByRole('img', { name: /Verified on attempt 2/ })).toBeVisible()

  // Back on the Workbench the getting-started card is done and gone
  await page.goto('/')
  await expect(page.getByRole('heading', { name: /first verified run/ })).toHaveCount(0)

  // And the account can be deleted, taking everything with it
  await page.goto('/settings')
  await page.getByRole('button', { name: 'delete my account' }).click()
  await page.getByLabel('type your password to confirm').fill(password)
  await page.getByRole('button', { name: 'delete everything' }).click()
  await expect(page).toHaveURL(/\/welcome/)
})

test('the operator gets an admin page with every account, and legal pages are marked as drafts', async ({ page }) => {
  // Local development without keys is run by its operator
  await page.goto('/admin')
  await expect(page.getByRole('heading', { name: 'Accounts' })).toBeVisible()
  await expect(page.getByRole('table', { name: 'Accounts' })).toBeVisible()
  await expect(page.getByText(/^\d+ accounts$/)).toBeVisible()

  for (const path of ['/terms', '/privacy', '/acceptable-use']) {
    await page.goto(path)
    await expect(page.getByText('DRAFT: needs human review.')).toBeVisible()
  }
})
