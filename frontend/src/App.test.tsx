import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from './auth'
import App from './App'

const profile = {
  id: 'c6b39e42-4bac-4690-92b8-104fb7055d5e', username: 'student',
  email: 'student@example.com', display_name: '', school: '', grade: '', roles: ['Student'],
}

beforeEach(() => {
  vi.stubGlobal('matchMedia', () => ({
    matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  localStorage.clear()
})

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function renderApp(path: string, queryClient = new QueryClient()) {
  render(<QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={[path]}><AuthProvider><App /></AuthProvider></MemoryRouter>
  </QueryClientProvider>)
  return queryClient
}

describe('S0 identity journey', () => {
  it('registers through the real form and shows the account', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/token/refresh/')) return new Response('{}', { status: 400 })
      if (url.endsWith('/auth/register/')) return Response.json({ access: 'test-access', user: profile }, { status: 201 })
      return new Response('{}', { status: 404 })
    })
    vi.stubGlobal('fetch', fetcher)
    renderApp('/register')
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'student' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'student@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'HardToGuess#2026' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tạo tài khoản' }))
    await waitFor(() => expect(screen.getByText('Xin chào, student')).toBeTruthy())
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('/auth/register/'),
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
  })

  it('keeps the user on the login page after a server error', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/token/refresh/')) return new Response('{}', { status: 400 })
      return Response.json({ error: { details: 'Thông tin đăng nhập không đúng.' } }, { status: 401 })
    })
    vi.stubGlobal('fetch', fetcher)
    renderApp('/login')
    fireEvent.change(screen.getByLabelText('Tên đăng nhập hoặc email'), { target: { value: 'student' } })
    expect(screen.queryByLabelText('Mật khẩu')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Tiếp tục' }))
    expect(screen.getByText('student')).toBeTruthy()
    expect(fetcher).not.toHaveBeenCalledWith(expect.stringContaining('/auth/login/'), expect.anything())
    fireEvent.click(screen.getByRole('button', { name: 'Đổi tài khoản' }))
    expect((screen.getByLabelText('Tên đăng nhập hoặc email') as HTMLInputElement).value).toBe('student')
    fireEvent.click(screen.getByRole('button', { name: 'Tiếp tục' }))
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Thông tin đăng nhập không đúng.'))
    expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeTruthy()
  })

  it('drops cached private data when signing out', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/token/refresh/')) return new Response('{}', { status: 400 })
      if (url.endsWith('/auth/register/')) return Response.json({ access: 'test-access', user: profile }, { status: 201 })
      if (url.endsWith('/auth/logout/')) return new Response(null, { status: 204 })
      return new Response('{}', { status: 404 })
    })
    vi.stubGlobal('fetch', fetcher)
    const queryClient = renderApp('/register')
    fireEvent.change(screen.getByLabelText('Tên đăng nhập'), { target: { value: 'student' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'student@example.com' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'HardToGuess#2026' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tạo tài khoản' }))
    await waitFor(() => expect(screen.getByText('Xin chào, student')).toBeTruthy())
    queryClient.setQueryData(['session', 'private', profile.id], { secret: 'owner-only' })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Đăng xuất' }))
    await waitFor(() => expect(queryClient.getQueryData(['session', 'private', profile.id])).toBeUndefined())
    expect(fetcher).toHaveBeenCalledWith(expect.stringContaining('/auth/logout/'), expect.objectContaining({ method: 'POST' }))
  })
})
