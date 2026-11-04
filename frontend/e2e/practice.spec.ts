import { expect, test } from '@playwright/test'

test('manual exam to timed result uses real API and database', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `solver${suffix}`
  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(owner)
  await page.getByLabel('Email').fill(`${owner}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible()

  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(`Bài làm ${suffix}`)
  await page.getByLabel('Nội dung').fill('Hai cộng hai bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Năm')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Sáu')
  await page.getByLabel('Đáp án đúng').selectOption('B')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: `Bài làm ${suffix}` })).toBeVisible()

  await page.getByRole('button', { name: 'Làm bài có giờ' }).click()
  await expect(page.getByRole('heading', { name: 'Bài làm của bạn' })).toBeVisible()
  await expect(page.getByText('Hai cộng hai bằng bao nhiêu?')).toBeVisible()
  await expect(page.getByText('Đáp án: B')).toHaveCount(0)
  const sessionUrl = page.url()
  await page.getByRole('radio', { name: 'B Bốn' }).check()
  await page.getByRole('button', { name: 'Lưu câu trả lời' }).click()
  await expect(page.getByRole('button', { name: '1' })).toHaveClass(/answered/)
  await page.reload()
  await expect(page.getByRole('radio', { name: 'B Bốn' })).toBeChecked()
  await expect(page.getByText('Đáp án: B')).toHaveCount(0)

  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Nộp bài' }).click()
  await expect(page.getByRole('heading', { name: 'Kết quả bài làm' })).toBeVisible()
  await expect(page.getByText('10.00 / 10.00')).toBeVisible()
  await expect(page.getByText('Đáp án: B')).toBeVisible()
  await page.goto(sessionUrl)
  await expect(page.getByRole('link', { name: 'Xem kết quả' })).toBeVisible()
})
