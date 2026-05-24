import { MachineDetail, MachinesResponse } from '../types/machine'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface MachineRequestResponse {
  assigned_machine: MachineDetail
  reserved_until: string
}

async function authFetch<T>(path: string, token: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${token}`, ...options.headers },
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}

export function getMachines(token: string): Promise<MachinesResponse> {
  return authFetch('/machines', token)
}

export function requestMachine(token: string): Promise<MachineRequestResponse> {
  return authFetch('/machines/request', token, { method: 'POST' })
}