import { useAuthStore } from '../store/authStore'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface TokenResponse {
  access_token: string
  token_type: string
  username: string
  gender: string
  role: string
}

export interface RegisterResponse {
  message: string
  email: string
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}

export function register(username: string, password: string, gender: string, email: string): Promise<RegisterResponse> {
  return postJson('/auth/register', { username, password, gender, email })
}

export function verifyEmail(email: string, code: string): Promise<TokenResponse> {
  return postJson('/auth/verify-email', { email, code })
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return postJson('/auth/login', { username, password })
}

async function patchJson<T>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  })
  if (res.status === 401) {
    useAuthStore.getState().logout()
    throw new Error('로그인이 만료되었습니다. 다시 로그인해주세요.')
  }
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}

export function changePassword(token: string, currentPassword: string, newPassword: string): Promise<{ message: string }> {
  return patchJson('/auth/password', { current_password: currentPassword, new_password: newPassword }, token)
}

export function changeUsername(token: string, currentPassword: string, newUsername: string): Promise<TokenResponse> {
  return patchJson('/auth/username', { current_password: currentPassword, new_username: newUsername }, token)
}
