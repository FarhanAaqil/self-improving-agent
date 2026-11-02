import { expect, test } from '@playwright/test'

const TASK = 'Write add(a, b) returning the sum'

test('a task fails, gets diagnosed, is repaired and verified, live @mobile', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Task description').fill(TASK)
  await page.keyboard.press('Control+Enter')

  await expect(page).toHaveURL(/\/runs\/run_/)
  // The story streams in over SSE: tests first, a failure, a diagnosis, then the fix
  await expect(page.getByText('Wrote 3 spec tests.')).toBeVisible()
  await expect(page.getByText('I subtracted where the task asks for a sum.')).toBeVisible()
  await expect(page.getByText('Verified on attempt 2.')).toBeVisible()
  await expect(page.getByRole('img', { name: /Verified on attempt 2/ })).toBeVisible()
  await expect(page.getByText('Passed 3/3 spec tests on attempt 2')).toBeVisible()
  await expect(page.getByRole('tab', { name: /attempt 1/ })).toBeVisible()
})

test('the diff between attempts shows the actual fix', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Task description').fill(TASK)
  await page.getByRole('button', { name: 'run it' }).click()
  await expect(page.getByText('Passed 3/3 spec tests on attempt 2')).toBeVisible()

  await page.getByRole('tab', { name: 'diff' }).click()
  const diff = page.locator('pre')
  await expect(diff.getByText('return a - b', { exact: true })).toBeVisible()
  await expect(diff.getByText('return a + b', { exact: true })).toBeVisible()
})

test('a verified run can be shared publicly and the link opens read-only', async ({ page, browser }) => {
  await page.goto('/')
  await page.getByLabel('Task description').fill(TASK)
  await page.getByRole('button', { name: 'run it' }).click()
  await expect(page.getByText('Passed 3/3 spec tests on attempt 2')).toBeVisible()

  await page.getByRole('button', { name: 'share link' }).click()
  const link = await page.getByRole('link', { name: /\/shared\// }).getAttribute('href')
  expect(link).toMatch(/^\/shared\//)

  // A stranger with no API key and no history
  const visitor = await browser.newPage()
  await visitor.goto(new URL(link!, page.url()).toString())
  await expect(visitor.getByText('shared, read-only')).toBeVisible()
  await expect(visitor.getByText('verification certificate')).toBeVisible()
  await expect(visitor.getByText(/sha256 [0-9a-f]{64}/)).toBeVisible()
})

test('the ledger lists runs and opens them', async ({ page }) => {
  await page.goto('/history')
  await expect(page.getByRole('heading', { name: 'Every run, on the record' })).toBeVisible()
  await page.getByRole('link', { name: TASK }).first().click()
  await expect(page).toHaveURL(/\/runs\/run_/)
})

test('launching a real attack on the security page shows it blocked', async ({ page }) => {
  await page.goto('/security')
  const row = page.getByRole('listitem').filter({ hasText: 'Become root' })
  await row.getByRole('button', { name: 'launch' }).click()
  await expect(row.getByText(/Blocked/)).toBeVisible()
})

test('night shift theme and command palette', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Switch to dark theme/ }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.keyboard.press('Control+k')
  await page.getByRole('combobox').fill('benchmarks')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/eval$/)
})
