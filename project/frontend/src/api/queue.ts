const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface QueueJoinResponse {
  queue_position: number
  total: number
  message: string
}

export interface QueueLeaveResponse {
  message: string
}

async function authFetch<T>(path: string, token: string, method: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}

export function joinQueue(token: string): Promise<QueueJoinResponse> {
  return authFetch('/queue/join', token, 'POST')
}

export function leaveQueue(token: string): Promise<QueueLeaveResponse> {
  return authFetch('/queue/leave', token, 'DELETE')
}