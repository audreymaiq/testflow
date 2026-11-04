import { expect, test } from '@playwright/test'

test('manual exam stays private across catalog and detail routes', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `owner${suffix}`
  const password = 'Zebra!Planet#42'

  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(owner)
  await page.getByLabel('Email').fill(`${owner}@example.test`)
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible()

  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(`Đề riêng tư ${suffix}`)
  await page.getByLabel('Nội dung').fill('Hai cộng hai bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Năm')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Sáu')
  await page.getByLabel('Đáp án đúng').selectOption('B')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: `Đề riêng tư ${suffix}` })).toBeVisible()
  const detailUrl = page.url()

  await page.goto('/library')
  await expect(page.getByText(`Đề riêng tư ${suffix}`)).toBeVisible()
  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()
  await page.goto(detailUrl)
  await expect(page.getByRole('heading', { name: 'Không thể mở đề' })).toBeVisible()
  await page.goto('/library')
  await expect(page.getByText(`Đề riêng tư ${suffix}`)).toHaveCount(0)

  const other = `other${suffix}`
  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(other)
  await page.getByLabel('Email').fill(`${other}@example.test`)
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${other}` })).toBeVisible()
  await page.goto(detailUrl)
  await expect(page.getByRole('heading', { name: 'Không thể mở đề' })).toBeVisible()
  await page.goto('/library')
  await expect(page.getByText(`Đề riêng tư ${suffix}`)).toHaveCount(0)
})
