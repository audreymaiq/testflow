import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python'

test('admin sees live operations counts after a private TXT upload', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const username = `opsuser${suffix}`
  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Email').fill(`${username}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible()
  const code = `from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; u=get_user_model().objects.get(username='${username}'); u.is_staff=True; u.save(update_fields=['is_staff']); u.groups.add(Group.objects.get(name='Admin'))`
  execFileSync(python, ['backend/manage.py', 'shell', '-c', code], { cwd: root })
  await page.reload()
  await page.getByLabel('Mở menu tài khoản').click()
  await expect(page.getByRole('link', { name: 'Vận hành' })).toBeVisible()
  await page.goto('/imports/new')
  const content = `#TITLE: Ops ${suffix}\n[C1] Math\nQuestion?\nA. One\nB. Two\n=>B\n`
  await page.getByLabel('Chọn tệp .txt').setInputFiles({ name: `ops-${suffix}.txt`, mimeType: 'text/plain', buffer: Buffer.from(content) })
  await page.getByRole('button', { name: 'Xác nhận' }).click()
  await expect(page.getByRole('heading', { name: `Ops ${suffix}` })).toBeVisible()
  await page.getByLabel('Mở menu tài khoản').click()
  await page.getByRole('link', { name: 'Vận hành' }).click()
  await expect(page.getByRole('heading', { name: 'Tình trạng hệ thống' })).toBeVisible()
  await expect(page.getByText('Chờ kiểm tra', { exact: true })).toBeVisible()
  await expect(page.getByText(/Yêu cầu công khai chờ duyệt:/)).toBeVisible()
})
