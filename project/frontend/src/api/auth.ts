const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface TokenResponse {
  access_token: string
  token_type: string
  username: string
  gender: string
  role: string
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

export function register(username: string, password: string, gender: string): Promise<TokenResponse> {
  return postJson('/auth/register', { username, password, gender })
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return postJson('/auth/login', { username, password })
}