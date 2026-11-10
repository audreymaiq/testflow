export type User = {
  id: string
  username: string
  email: string
  display_name: string
  school: string
  grade: string
  roles: string[]
}

export type Session = { access: string; user: User }

const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

function errorMessage(body: unknown): string {
  if (typeof body !== 'object' || body === null) return 'Có lỗi kết nối. Vui lòng thử lại.'
  const record = body as Record<string, unknown>
  const nested = record.error
  if (typeof nested === 'object' && nested !== null) {
    const message = (nested as Record<string, unknown>).message
    if (typeof message === 'string') return message
    const details = (nested as Record<string, unknown>).details
    if (typeof details === 'string') return details
    if (typeof details === 'object' && details !== null) {
      return Object.values(details as Record<string, unknown>).flat().map(String).join(' ')
    }
  }
  return 'Có lỗi kết nối. Vui lòng thử lại.'
}

export async function request<T>(path: string, options: RequestInit = {}, access?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      credentials: 'include',
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        ...(access ? { Authorization: `Bearer ${access}` } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new ApiError('Không kết nối được máy chủ. Vui lòng thử lại.', 0)
  }
  if (response.status === 204) return undefined as T
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(errorMessage(body), response.status)
  return body as T
}

export async function requestBlob(path: string, access?: string): Promise<Blob> {
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      credentials: 'include',
      headers: access ? { Authorization: `Bearer ${access}` } : {},
    })
  } catch {
    throw new ApiError('Không kết nối được máy chủ. Vui lòng thử lại.', 0)
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(errorMessage(body), response.status)
  }
  return response.blob()
}
