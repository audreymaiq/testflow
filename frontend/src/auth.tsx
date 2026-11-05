import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError, request, type Session, type User } from './api'

let bootstrapPromise: Promise<Session> | null = null
let refreshPromise: Promise<{ access: string }> | null = null

function rotateRefresh() {
  if (!refreshPromise) {
    refreshPromise = request<{ access: string }>('/auth/token/refresh/', { method: 'POST' })
      .finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

function bootstrapSession(): Promise<Session> {
  if (!bootstrapPromise) {
    bootstrapPromise = rotateRefresh()
      .then(async ({ access }) => ({ access, user: await request<User>('/auth/me/', {}, access) }))
      .finally(() => { bootstrapPromise = null })
  }
  return bootstrapPromise
}

type AuthContextValue = {
  user: User | null
  access: string | null
  loading: boolean
  register: (username: string, email: string, password: string) => Promise<void>
  login: (identifier: string, password: string) => Promise<void>
  logout: () => Promise<void>
  updateProfile: (profile: Pick<User, 'display_name' | 'school' | 'grade'>) => Promise<void>
  api: <T>(path: string, options?: RequestInit) => Promise<T>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [access, setAccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const sessionVersion = useRef(0)

  useEffect(() => {
    let active = true
    bootstrapSession()
      .then(({ access: token, user: profile }) => {
        if (active && sessionVersion.current === 0) { setAccess(token); setUser(profile) }
      })
      .catch(() => { if (active && sessionVersion.current === 0) { setAccess(null); setUser(null) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function register(username: string, email: string, password: string) {
    const session = await request<Session>('/auth/register/', {
      method: 'POST', body: JSON.stringify({ username, email, password }),
    })
    sessionVersion.current += 1
    setAccess(session.access); setUser(session.user)
  }

  async function login(identifier: string, password: string) {
    const session = await request<Session>('/auth/login/', {
      method: 'POST', body: JSON.stringify({ identifier, password }),
    })
    sessionVersion.current += 1
    setAccess(session.access); setUser(session.user)
  }

  async function logout() {
    await request<void>('/auth/logout/', { method: 'POST' })
    sessionVersion.current += 1
    setAccess(null); setUser(null)
  }

  async function updateProfile(profile: Pick<User, 'display_name' | 'school' | 'grade'>) {
    const canonical = await api<{ school: string }>('/taxonomy/profile-school/', {
      method: 'POST', body: JSON.stringify({ name: profile.school }),
    })
    const updated = await api<User>('/auth/me/', {
      method: 'PATCH', body: JSON.stringify({ display_name: profile.display_name, grade: profile.grade }),
    })
    setUser({ ...updated, school: canonical.school })
  }

  async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
    try {
      return await request<T>(path, options, access || undefined)
    } catch (cause) {
      if (!(cause instanceof ApiError) || cause.status !== 401 || !user) throw cause
      try {
        const refreshed = await rotateRefresh()
        setAccess(refreshed.access)
        return await request<T>(path, options, refreshed.access)
      } catch (refreshError) {
        setAccess(null); setUser(null)
        throw refreshError
      }
    }
  }

  return <AuthContext.Provider value={{ user, access, loading, register, login, logout, updateProfile, api }}>
    {children}
  </AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider is required')
  return context
}
