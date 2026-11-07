import { useEffect, useState } from 'react'

type Mode = 'light' | 'dark'

export function ModeControl() {
  const [mode, setMode] = useState<Mode>(() =>
    document.documentElement.dataset.mode === 'dark' ? 'dark' : 'light')

  useEffect(() => {
    document.documentElement.dataset.mode = mode
    localStorage.setItem('tf_mode', mode)
    localStorage.removeItem('tf_theme')
  }, [mode])

  return <button className="mode-control" type="button" aria-pressed={mode === 'dark'}
    aria-label={mode === 'light' ? 'Chuyển sang chế độ tối' : 'Chuyển sang chế độ sáng'}
    onClick={() => setMode((current) => current === 'light' ? 'dark' : 'light')}>
    {mode === 'light'
      ? <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M19.5 15.4A8 8 0 0 1 8.6 4.5 8 8 0 1 0 19.5 15.4Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" /></svg>
      : <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="3.7" stroke="currentColor" strokeWidth="1.7" /><path d="M12 1.7v2m0 16.6v2M1.7 12h2m16.6 0h2M4.7 4.7l1.4 1.4m11.8 11.8 1.4 1.4m0-14.6-1.4 1.4M6.1 17.9l-1.4 1.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>}
    <span>{mode === 'light' ? 'Tối' : 'Sáng'}</span>
  </button>
}
