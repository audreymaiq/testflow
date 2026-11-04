import { useEffect, useState } from 'react'

const themes = ['ocean', 'amber', 'sakura', 'holo'] as const
const modes = ['light', 'dark', 'system'] as const
type Theme = typeof themes[number]
type Mode = typeof modes[number]

function getStored<T extends string>(key: string, values: readonly T[], fallback: T): T {
  const value = localStorage.getItem(key)
  return values.find((item) => item === value) ?? fallback
}

export function ThemeControls() {
  const [theme, setTheme] = useState<Theme>(() => getStored('tf_theme', themes, 'ocean'))
  const [mode, setMode] = useState<Mode>(() => getStored('tf_mode', modes, 'system'))

  useEffect(() => {
    const query = matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      document.documentElement.dataset.theme = theme
      document.documentElement.dataset.mode = mode === 'system' ? (query.matches ? 'dark' : 'light') : mode
    }
    localStorage.setItem('tf_theme', theme)
    localStorage.setItem('tf_mode', mode)
    apply()
    query.addEventListener('change', apply)
    return () => query.removeEventListener('change', apply)
  }, [theme, mode])

  return <div className="theme-controls">
    <label>Giao diện
      <select value={theme} onChange={(event) => setTheme(event.target.value as Theme)}>
        <option value="ocean">Cobalt</option><option value="amber">Bronze</option>
        <option value="sakura">Rose</option><option value="holo">Violet</option>
      </select>
    </label>
    <label>Chế độ
      <select value={mode} onChange={(event) => setMode(event.target.value as Mode)}>
        <option value="light">Sáng</option><option value="dark">Tối</option>
        <option value="system">Tự động</option>
      </select>
    </label>
  </div>
}
