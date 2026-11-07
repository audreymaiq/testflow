import { expect, test } from '@playwright/test'

test('school and major selectors filter a private exam together', async ({ page }) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`
  const owner = `facets${suffix}`
  const title = `Đề lọc ${suffix}`
  const school = `Trường Mẫu ${suffix}`
  const major = `Ngành Mẫu ${suffix}`
  await page.goto('/register')
  await page.getByLabel('Tên đăng nhập', { exact: true }).fill(owner)
  await page.getByLabel('Email').fill(`${owner}@example.test`)
  await page.getByLabel('Mật khẩu').fill('Zebra!Planet#42')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible()

  await page.goto('/exams/new')
  await page.getByLabel('Tên đề').fill(title)
  await page.getByLabel('Thêm trường').fill(school)
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Tạo tên mới' }).click()
  await page.getByLabel('Thêm ngành').fill(major)
  await page.getByRole('group', { name: 'Ngành' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await page.getByRole('group', { name: 'Ngành' }).getByRole('button', { name: 'Tạo tên mới' }).click()
  await page.getByLabel('Nội dung').fill('Một cộng một bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Một')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Hai')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án đúng', { exact: true }).selectOption('B')
  await page.getByRole('button', { name: 'Tạo đề riêng tư' }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()

  await page.goto('/library')
  const schoolSelect = page.locator('.library-filters').getByLabel('Trường')
  const majorSelect = page.locator('.library-filters').getByLabel('Ngành')
  await expect(schoolSelect.locator('option', { hasText: school })).toContainText('(1)')
  await expect(majorSelect.locator('option', { hasText: major })).toContainText('(1)')
  await schoolSelect.selectOption(school)
  await majorSelect.selectOption(major)
  await expect(schoolSelect).toHaveValue(school)
  await expect(majorSelect).toHaveValue(major)
  await expect(page.getByText(title)).toBeVisible()
  expect(new URL(page.url()).searchParams.get('school')).toBe(school)
  expect(new URL(page.url()).searchParams.get('major')).toBe(major)
  await page.reload()
  await expect(schoolSelect).toHaveValue(school)
  await expect(majorSelect).toHaveValue(major)
  await expect(page.getByText(title)).toBeVisible()
  await page.setViewportSize({ width: 360, height: 800 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(360)
  await schoolSelect.selectOption('')
  await expect(majorSelect).toHaveValue(major)
  await expect(page.getByText(title)).toBeVisible()
})

test('manual exam stays private across catalog and detail routes', async ({ page }) => {
  test.setTimeout(90000)
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
  await page.getByLabel('Thêm trường').fill(`Trường Mẫu ${suffix}`)
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Kiểm tra tên' }).click()
  await page.getByRole('group', { name: 'Trường' }).getByRole('button', { name: 'Tạo tên mới' }).click()
  await page.getByLabel('Nội dung').fill('Hai cộng hai bằng bao nhiêu?')
  await page.getByLabel('Đáp án A', { exact: true }).fill('Ba')
  await page.getByLabel('Đáp án B', { exact: true }).fill('Bốn')
  await page.getByLabel('Đáp án C', { exact: true }).fill('Năm')
  await page.getByLabel('Đáp án D', { exact: true }).fill('Sáu')
  await page.getByLabel('Đáp án đúng', { exact: true }).selectOption('B')
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

  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('link', { name: 'Đăng nhập' })).toBeVisible()
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập hoặc email').fill(owner)
  await page.getByRole('button', { name: 'Tiếp tục' }).click()
  await page.getByLabel('Mật khẩu').fill(password)
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click()
  await expect(page.getByRole('heading', { name: `Xin chào, ${owner}` })).toBeVisible({ timeout: 15000 })
  await page.goto(detailUrl)
  await page.getByRole('button', { name: 'Xóa đề' }).click()
  const confirmation = page.getByRole('dialog', { name: 'Xóa đề?' })
  await expect(confirmation).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(confirmation).toBeHidden()
  await expect(page.getByRole('heading', { name: `Đề riêng tư ${suffix}` })).toBeVisible()
  await page.getByRole('button', { name: 'Xóa đề' }).click()
  await confirmation.getByRole('button', { name: 'Xác nhận xóa' }).click()
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByText(`Đề riêng tư ${suffix}`)).toHaveCount(0)
})

test('pagination remains visible and keeps page navigation usable', async ({ page }) => {
  let hasNext = false
  const exam = {
    id: '00000000-0000-4000-8000-000000000001', title: 'Đề minh họa', subtitle: '',
    level: 'THPT', grade: 12, icon: '', color: '', subject: 'Toán', exam_type: 'ON_TAP',
    visibility: 'PUBLIC', question_count: 1, duration_minutes: 30, has_answer_key: true,
    year: null, is_system_sample: false,
  }
  await page.route('**/api/v1/exams/?*', async (route) => {
    const current = new URL(route.request().url()).searchParams.get('page') === '2'
    await route.fulfill({ json: {
      count: hasNext ? 12 : 1,
      next: hasNext && !current ? '?page=2' : null,
      previous: current ? '?page=1' : null,
      results: [exam],
    } })
  })

  await page.goto('/library')
  await expect(page.locator('.result-count')).toHaveText('Tìm thấy 1 đề')
  const pagination = page.getByRole('navigation', { name: 'Phân trang đề thi' })
  await expect(pagination).toBeVisible()
  await expect(pagination.getByRole('button', { name: 'Trang trước' })).toBeDisabled()
  await expect(pagination.getByRole('button', { name: 'Trang sau' })).toBeDisabled()

  hasNext = true
  await page.reload()
  await expect(pagination).toBeVisible()
  await pagination.getByRole('button', { name: 'Trang sau' }).click()
  await expect(page).toHaveURL(/page=2/)
  await expect(pagination.locator('[aria-current="page"]')).toHaveText('2')
  await pagination.getByRole('button', { name: 'Trang trước' }).click()
  await expect(page).not.toHaveURL(/page=2/)
  await page.setViewportSize({ width: 320, height: 700 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
  await expect(pagination.getByRole('button', { name: 'Trang sau' })).toBeVisible()
})
