import { expect, test } from '@playwright/test'

test('mobile catalog keeps search and theme controls usable without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.goto('/library')
  const filters = page.locator('.library-filters')
  const toggle = filters.getByRole('button', { name: 'Hiện bộ lọc' })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(filters.locator('input[type=search]')).toBeHidden()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)

  await toggle.click()
  await expect(filters.getByRole('button', { name: 'Ẩn bộ lọc' })).toHaveAttribute('aria-expanded', 'true')
  await filters.locator('input[type=search]').fill('khong-co-de-nay')
  await expect(page).toHaveURL(/q=khong-co-de-nay/)
  await expect(page.getByRole('button', { name: 'Bỏ lọc Tìm: khong-co-de-nay' })).toBeVisible()
  await filters.getByRole('button', { name: 'Xóa bộ lọc' }).click()
  await expect(page).not.toHaveURL(/q=/)

  await page.getByLabel('Chế độ').selectOption('dark')
  await expect(page.locator('html')).toHaveAttribute('data-mode', 'dark')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})
