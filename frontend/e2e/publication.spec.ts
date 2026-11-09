import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const root = fileURLToPath(new URL('../..', import.meta.url))
const python = process.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python'

async function register(page: import('@playwright/test').Page, username: string) {
  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(username)
  await page.getByLabel('Email').fill(`${username}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${username}` })).toBeVisible()
}

async function logout(page: import('@playwright/test').Page) {
  const accountMenu = page.locator('details.header-account')
  if (await accountMenu.getAttribute('open') === null) await page.getByLabel('Mở menu tài khoản').click()
  await accountMenu.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
}

test('owner publication request is approved by reviewer and private withdrawal is immediate', async ({ page }) => {
  test.setTimeout(90000)
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `publisher${suffix}`
  const reviewer = `reviewer${suffix}`
  await register(page, owner)
  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(`Đề duyệt ${suffix}`)
  await page.getByLabel('Thêm trường').fill(`Trường Mẫu ${suffix}`)
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Tạo tên mới' }).click()
  await page.getByLabel('Nội dung').fill('Một cộng một bằng mấy?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Một')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Hai')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án đúng', { exact: true }).selectOption('B')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: `Đề duyệt ${suffix}` })).toBeVisible()
  const examUrl = page.url()
  await page.getByRole('button', { name: 'Gửi duyệt công khai' }).click()
  await expect(page.getByText(/Đã gửi yêu cầu công khai/)).toBeVisible()
  await logout(page)

  await register(page, reviewer)
  const code = `from django.contrib.auth import get_user_model; from django.contrib.auth.models import Group; get_user_model().objects.get(username='${reviewer}').groups.add(Group.objects.get(name='Reviewer'))`
  execFileSync(python, ['backend/manage.py', 'shell', '-c', code], { cwd: root })
  await page.reload()
  await page.getByLabel('Mở menu tài khoản').click()
  await page.getByRole('link', { name: 'Duyệt đề' }).click()
  await expect(page.getByText(`Đề duyệt ${suffix}`)).toBeVisible()
  await page.getByRole('article').filter({ hasText: `Đề duyệt ${suffix}` }).getByRole('link', { name: 'Xem và duyệt' }).click()
  await expect(page.getByText('Nguồn: Tự biên soạn', { exact: true })).toBeVisible()
  await expect(page.getByText('Một cộng một bằng mấy?')).toBeVisible()
  await page.getByRole('button', { name: 'Duyệt công khai' }).click()
  await expect(page.getByText(`Đề duyệt ${suffix}`)).toHaveCount(0)
  await logout(page)

  await page.goto(examUrl)
  await expect(page.getByRole('heading', { name: `Đề duyệt ${suffix}` })).toBeVisible()
  await page.getByRole('link', { name: 'Đăng nhập để luyện tập' }).click()
  await expect(page.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
  await page.getByRole('link', { name: 'Tạo tài khoản' }).last().click()
  const learner = `learner${suffix}`
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(learner)
  await page.getByLabel('Email').fill(`${learner}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: 'Bài làm của bạn' })).toBeVisible()
  await expect(page.getByText('LUYỆN TẬP', { exact: true })).toBeVisible()
  await page.goto(examUrl)
  await expect(page.getByText(/1 lượt làm · 0 câu trong ngân hàng câu sai/)).toBeVisible()
  await logout(page)
  await page.goto('/add-exam')
  await expect(page.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
  await page.getByLabel('Tên đăng nhập hoặc email').fill(learner)
  await page.getByRole('button', { name: 'Tiếp tục' }).click()
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Thêm đề', exact: true })).toBeVisible()
  await logout(page)

  await page.goto(examUrl)
  await page.getByRole('link', { name: 'Đăng nhập để làm bài có giờ' }).click()
  await page.getByLabel('Tên đăng nhập hoặc email').fill(owner)
  await page.getByRole('button', { name: 'Tiếp tục' }).click()
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Bài làm của bạn' })).toBeVisible()
  await expect(page.getByText('LÀM BÀI CÓ GIỜ', { exact: true })).toBeVisible()
  await page.goto(examUrl)
  await page.getByRole('button', { name: 'Chuyển về riêng tư' }).click()
  const withdraw = page.getByRole('dialog', { name: 'Chuyển về riêng tư?' })
  await expect(withdraw).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(withdraw).toBeHidden()
  await expect(page.getByRole('button', { name: 'Chuyển về riêng tư' })).toBeVisible()
  await page.getByRole('button', { name: 'Chuyển về riêng tư' }).click()
  await withdraw.getByRole('button', { name: 'Xác nhận chuyển' }).click()
  await expect(page.getByText('Đề đã chuyển về riêng tư.')).toBeVisible()
  await logout(page)
  await page.goto(examUrl)
  await expect(page.getByRole('heading', { name: 'Không thể mở đề' })).toBeVisible()
})
