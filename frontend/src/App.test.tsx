import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

describe('S0 identity journey', () => {
  it('registers through the real form and shows the account', async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith('/auth/token/refresh/')) return new Response('{}', { status: 400 })
      if (url.endsWith('/auth/register/')) return Response.json({ access: 'test-access', user: profile }, { status: 201 })
      return new Response('{}', { status: 404 })
    })
    vi.stubGlobal('fetch', fetcher)
    render(<MemoryRouter initialEntries={['/register']}><AuthProvider><App /></AuthProvider></MemoryRouter>)
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
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/auth/token/refresh/')) return new Response('{}', { status: 400 })
      return Response.json({ error: { details: 'Thông tin đăng nhập không đúng.' } }, { status: 401 })
    }))
    render(<MemoryRouter initialEntries={['/login']}><AuthProvider><App /></AuthProvider></MemoryRouter>)
    fireEvent.change(screen.getByLabelText('Tên đăng nhập hoặc email'), { target: { value: 'student' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrongpass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Thông tin đăng nhập không đúng.'))
    expect(screen.getByRole('heading', { name: 'Đăng nhập' })).toBeTruthy()
  })
})
