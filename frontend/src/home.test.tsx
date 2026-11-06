import { afterEach, expect, it } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { DeckMark } from './home'

afterEach(cleanup)

it('maps the authorized legacy eye icon to an SVG mark', () => {
  const { container } = render(<DeckMark title="Thị Giác Máy Tính" icon="👁️" color="#c9a84b" />)
  expect(container.querySelector('svg')).not.toBeNull()
  expect(container.textContent).not.toContain('👁')
  expect((container.firstChild as HTMLElement).style.borderColor).toBe('rgb(201, 168, 75)')
})

it('uses a safe monogram for unsupported user icons and colors', () => {
  const { container } = render(<DeckMark title="Thị Giác" icon="🧠" color="red;position:fixed" />)
  expect(container.querySelector('svg')).toBeNull()
  expect(container.textContent).toBe('TH')
  expect((container.firstChild as HTMLElement).style.borderColor).toBe('')
})
