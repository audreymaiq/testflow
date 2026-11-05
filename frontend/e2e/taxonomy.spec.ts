import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python'

test('user proposes a school, Admin approves it, and the exam uses its canonical name', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `taxonomy${suffix}`
  const admin = `taxadmin${suffix}`
  const password = 'Zebra!Planet#42'
  const school = `Trường Kiểm Chứng ${suffix}`

  async function register(username: string) {
    await page.goto('/register')
    await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
    await page.getByLabel('Email').fill(`${username}@example.test`)
    await page.getByLabel('Mật khẩu').fill(password)
    await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
    await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible()
  }
  async function logout() {
    await page.getByRole('button', { name: 'Đăng xuất' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  }

  await register(owner)
  await page.goto('/exams/new')
  await page.getByLabel('Thêm trường').fill(school)
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await expect(page.getByRole('button', { name: 'Đề xuất tên mới' })).toBeVisible()
  await page.getByRole('button', { name: 'Đề xuất tên mới' }).click()
  await expect(page.getByText(/Đã gửi đề xuất/)).toBeVisible()
  await logout()

  await register(admin)
  const code = `from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; u=get_user_model().objects.get(username='${admin}'); u.is_staff=True; u.save(update_fields=['is_staff']); u.groups.add(Group.objects.get_or_create(name='Admin')[0])`
  execFileSync(python, ['backend/manage.py', 'shell', '-c', code], { cwd: root })
  await page.reload()
  await expect(page.getByRole('link', { name: 'Vận hành' })).toBeVisible()
  await page.goto('/ops')
  const row = page.locator('.taxonomy-proposal').filter({ hasText: school })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Tạo tên chuẩn' }).click()
  await expect(row).toHaveCount(0)
  await logout()

  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập hoặc email').fill(owner)
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible()
  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(`Đề danh mục ${suffix}`)
  await page.getByLabel('Thêm trường').fill(school.toUpperCase())
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await expect(page.getByText(`Tên chuẩn: ${school}`)).toBeVisible()
  await page.getByLabel('Nội dung').fill('Một cộng một bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Một')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Hai')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Bốn')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: `Đề danh mục ${suffix}` })).toBeVisible()
  await expect(page.getByRole('definition').filter({ hasText: school })).toBeVisible()
})
