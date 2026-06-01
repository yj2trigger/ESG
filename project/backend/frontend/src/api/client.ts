import { useAuthStore } from '../store/authStore'

export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function authFetch<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...options.headers },
  })
  if (res.status === 401) {
    useAuthStore.getState().logout()
    throw new Error('로그인이 만료되었습니다. 다시 로그인해주세요.')
  }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}
