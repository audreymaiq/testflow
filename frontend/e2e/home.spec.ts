import { expect, test } from '@playwright/test'

test('home grid searches real exams and respects private ownership', async ({ page }) => {
  test.setTimeout(90000)
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `home${suffix}`
  const title = `Đề trang chủ ${suffix}`

  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(owner)
  await page.getByLabel('Email').fill(`${owner}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible()

  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(title)
  await page.getByLabel('Thêm trường').fill(`Trường Mẫu ${suffix}`)
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Tạo tên mới' }).click()
  await page.getByLabel('Nội dung').fill('Một cộng một bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Một')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Hai')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án đúng').selectOption('B')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Thư viện đề' })).toBeVisible()
  await page.getByLabel('Tìm bộ đề').fill(suffix)
  await page.getByRole('button', { name: 'Tìm đề' }).click()
  const card = page.locator('.home-deck', { hasText: title })
  await expect(card).toBeVisible()
  await expect(card).toContainText('0 chương · 1 câu')
  await expect(card).toContainText('Riêng tư')
  await page.setViewportSize({ width: 360, height: 780 })
  await expect(card).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()

  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog', { name: 'Đăng xuất?' }).getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()
  await page.goto('/')
  await page.getByLabel('Tìm bộ đề').fill(suffix)
  await page.getByRole('button', { name: 'Tìm đề' }).click()
  await expect(page.getByText('Không tìm thấy bộ đề phù hợp.')).toBeVisible()
  await expect(page.locator('.home-deck', { hasText: title })).toHaveCount(0)
})
