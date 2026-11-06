import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('registration, logout and login use the running API and PostgreSQL', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const username = `student${suffix}`
  const email = `${username}@example.test`
  const password = 'Zebra!Planet#42'

  await page.goto('/register')
  const registerAccessibility = await new AxeBuilder({ page }).analyze()
  expect(registerAccessibility.violations).toEqual([])
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible({ timeout: 15000 })
  await page.reload()
  await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible({ timeout: 15000 })
  await page.getByLabel('Tên hiển thị').fill('Người học thử nghiệm')
  await page.getByLabel('Lớp').fill('12A')
  await page.getByRole('button', { name: 'Lưu hồ sơ' }).click()
  await expect(page.getByRole('heading', { name: 'Xin chào, Người học thử nghiệm' })).toBeVisible()
  await page.setViewportSize({ width: 360, height: 800 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  const accountAccessibility = await new AxeBuilder({ page }).analyze()
  expect(accountAccessibility.violations).toEqual([])

  const cookies = await page.context().cookies()
  expect(cookies.find((cookie) => cookie.name === 'tf_refresh')?.httpOnly).toBe(true)
  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()

  await page.goto('/account')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Tên đăng nhập hoặc email').fill(email)
  await expect(page.getByLabel('Mật khẩu')).toHaveCount(0)
  await page.getByRole('button', { name: 'Tiếp tục' }).click()
  await expect(page.getByText(email)).toBeVisible()
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Xin chào, Người học thử nghiệm' })).toBeVisible()
})

test('theme choices persist across a reload', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Giao diện').selectOption('sakura')
  await page.getByLabel('Chế độ').selectOption('dark')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'sakura')
  await expect(page.locator('html')).toHaveAttribute('data-mode', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'sakura')
  await expect(page.locator('html')).toHaveAttribute('data-mode', 'dark')
})
