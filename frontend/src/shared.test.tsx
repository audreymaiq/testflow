import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Toast } from './shared'

beforeEach(() => vi.useFakeTimers())
afterEach(() => { cleanup(); vi.useRealTimers() })

it('pauses toast timeout on hover and resumes with remaining time', () => {
  const close = vi.fn()
  render(<Toast message="Đã lưu" onClose={close} durationMs={1000} />)
  act(() => vi.advanceTimersByTime(400))
  fireEvent.mouseEnter(screen.getByRole('status'))
  act(() => vi.advanceTimersByTime(2000))
  expect(close).not.toHaveBeenCalled()
  fireEvent.mouseLeave(screen.getByRole('status'))
  act(() => vi.advanceTimersByTime(600))
  expect(close).toHaveBeenCalledOnce()
})

it('keeps a focused toast open and offers an explicit close button', () => {
  const close = vi.fn()
  render(<Toast message="Đã lưu" onClose={close} durationMs={1000} />)
  fireEvent.focus(screen.getByRole('button', { name: 'Đóng thông báo' }))
  act(() => vi.advanceTimersByTime(1500))
  expect(close).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Đóng thông báo' }))
  expect(close).toHaveBeenCalledOnce()
})
