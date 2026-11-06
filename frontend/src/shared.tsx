import { useEffect, useRef, useState, type ReactNode } from 'react'

export function Toast({ message, onClose, durationMs = 5000 }: {
  message: string; onClose: () => void; durationMs?: number
}) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const paused = hovered || focused
  const [remainingMs, setRemainingMs] = useState(durationMs)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    if (paused) return
    const start = Date.now()
    const startRemaining = remainingMs
    const timer = window.setInterval(() => {
      const next = Math.max(0, startRemaining - (Date.now() - start))
      setRemainingMs(next)
      if (next === 0) closeRef.current()
    }, 100)
    return () => window.clearInterval(timer)
  }, [paused])

  return <div className="toast" role="status" onMouseEnter={() => setHovered(true)}
    onMouseLeave={() => setHovered(false)} onFocus={() => setFocused(true)}
    onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false) }}>
    <div className="toast-content"><span>{message}</span><button type="button" aria-label="Đóng thông báo" onClick={onClose}>×</button></div>
    <div className="toast-progress" aria-hidden="true"><span style={{ width: `${remainingMs / durationMs * 100}%` }} /></div>
  </div>
}

export function Modal({ title, children, onClose }: {
  title: string; children: ReactNode; onClose: () => void
}) {
  const closeButton = useRef<HTMLButtonElement>(null)
  const dialog = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    closeButton.current?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !dialog.current) return
      const focusable = Array.from(dialog.current.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea'))
        .filter((element) => !element.hasAttribute('disabled'))
      if (!focusable.length) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    window.addEventListener('keydown', handleKey)
    return () => { window.removeEventListener('keydown', handleKey); previous?.focus() }
  }, [onClose])
  return <div className="modal-backdrop" role="presentation">
    <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby="modal-title" className="modal">
      <h2 id="modal-title">{title}</h2>
      {children}
      <button ref={closeButton} type="button" onClick={onClose}>Đóng</button>
    </div>
  </div>
}
