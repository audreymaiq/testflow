import { useEffect, useRef, type ReactNode } from 'react'

export function Toast({ message }: { message: string }) {
  return <div className="toast" role="status">{message}</div>
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
