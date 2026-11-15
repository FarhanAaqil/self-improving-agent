import { expect, test } from '@playwright/test'
import { OUTBOX, signUp } from './mail'

test('a stranger signs up, confirms their email and makes an API key', async ({ page }) => {
  test.skip(!OUTBOX, 'set MAIL_OUTBOX_DIR for the server and the tests')
  const password = 'a long enough password'
  const email = await signUp(page, password)
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
