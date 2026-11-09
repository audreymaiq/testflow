import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('home and library share the same header scale and alignment', async ({ page }) => {
  await page.setViewportSize({ width: 1671, height: 941 })
  await page.goto('/')
  const homeHeader = await page.locator('.topbar-dashboard .topbar-inner').boundingBox()
  const homeNav = await page.locator('.topbar-dashboard nav').boundingBox()
  const homeHero = await page.locator('.home-hero').boundingBox()
  const homeImage = await page.locator('.home-hero-image').getAttribute('src')

  await page.goto('/library')
  const libraryHeader = await page.locator('.topbar-dashboard .topbar-inner').boundingBox()
  const libraryNav = await page.locator('.topbar-dashboard nav').boundingBox()
  const libraryHero = await page.locator('.library-hero').boundingBox()
  const libraryImage = await page.locator('.library-hero img').getAttribute('src')

  expect(libraryHeader).toEqual(homeHeader)
  expect(libraryNav?.x).toBe(homeNav?.x)
  expect(libraryImage).toBe(homeImage)
  expect(libraryHero!.width).toBeLessThan(homeHero!.width)
  expect(libraryHero!.width).toBeGreaterThan(homeHero!.width - 40)
  expect(libraryHero!.height).toBeLessThan(homeHero!.height)
})

test('mobile catalog keeps search and the mode toggle usable without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 })
  await page.addInitScript(() => localStorage.setItem('tf_mode', 'light'))
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

  await page.getByRole('button', { name: 'Chuyển sang chế độ tối' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-mode', 'dark')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})

test('guest discovery keeps primary actions visible and accessible on a narrow screen', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 780 })
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Tạo tài khoản', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tìm đề' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])

  await page.goto('/library')
  await expect(page.getByRole('button', { name: 'Hiện bộ lọc' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})

test('homepage remains usable with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Hôm nay, bạn muốn luyện tập gì?' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Tìm đề' })).toBeVisible()
})
