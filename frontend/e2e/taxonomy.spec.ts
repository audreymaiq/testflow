import { expect, test } from '@playwright/test'

test('users create new names themselves and reuse the same canonical records', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const password = 'Zebra!Planet#42'
  const subject = `Toán học ${suffix}`
  const school = `Trường Kiểm Chứng ${suffix}`
  const major = `Khoa học dữ liệu ${suffix}`

  async function register(username: string) {
    await page.goto('/register')
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
    await page.getByLabel('Email').fill(`${username}@example.test`)
    await page.getByLabel('Mật khẩu').fill(password)
    await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
    await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible()
  }

  await register(`taxonomyA${suffix}`)
  await page.goto('/exams/new')
  await page.getByLabel('Tên môn khác').fill(subject)
  await page.getByRole('button', { name: 'Kiểm tra tên' }).first().click()
  await page.getByRole('button', { name: 'Tạo tên mới' }).click()
  await expect(page.getByText(`Tên chuẩn: ${subject}`)).toBeVisible()

  for (const [group, label, name] of [['Trường', 'Thêm trường', school], ['Ngành', 'Thêm ngành', major]]) {
    const field = page.getByRole('group', { name: group })
    await field.getByLabel(label).fill(name)
    await field.getByRole('button', { name: 'Kiểm tra tên' }).click()
    await field.getByRole('button', { name: 'Tạo tên mới' }).click()
    await expect(field.locator('.taxonomy-chip').filter({ hasText: name })).toBeVisible()
  }

  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()
  await register(`taxonomyB${suffix}`)
  await page.getByLabel('Trường').fill(school.toUpperCase())
  await page.getByRole('button', { name: 'Kiểm tra tên' }).click()
  await expect(page.getByText(`Tên chuẩn: ${school}`)).toBeVisible()
  await page.getByRole('button', { name: 'Lưu hồ sơ' }).click()
  await expect(page.getByText('Đã lưu hồ sơ.')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Trường')).toHaveValue(school)

  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(`Đề danh mục ${suffix}`)
  await page.getByLabel('Tên môn khác').fill(subject.toUpperCase())
  await page.getByRole('button', { name: 'Kiểm tra tên' }).first().click()
  await expect(page.getByText(`Tên chuẩn: ${subject}`)).toBeVisible()
  for (const [group, label, name] of [['Trường', 'Thêm trường', school], ['Ngành', 'Thêm ngành', major]]) {
    const field = page.getByRole('group', { name: group })
    await field.getByLabel(label).fill(name.toUpperCase())
    await field.getByRole('button', { name: 'Kiểm tra tên' }).click()
    await expect(field.getByText(`Tên chuẩn: ${name}`)).toBeVisible()
  }
  await page.getByLabel('Nội dung').fill('Một cộng một bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Một')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Hai')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Bốn')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: `Đề danh mục ${suffix}` })).toBeVisible()
  await expect(page.getByText(school, { exact: true })).toBeVisible()
  await expect(page.getByText(major, { exact: true })).toBeVisible()
})
