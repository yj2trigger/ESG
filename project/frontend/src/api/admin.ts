import { authFetch } from './client'

export type MachineStatus = 'available' | 'in_use' | 'soft_reserved' | 'broken'

export interface AdminMachine {
  id: number
  floor: number
  machine_number: number
  status: MachineStatus
  gender_restriction: string | null
  reserved_by_user_id: number | null
  reserved_until: string | null
}

export interface PowerDataPoint {
  timestamp: string
  power_w: number
}

export interface AdminSettings {
  power_threshold_w: number
  stop_threshold_w: number
}

export function adminGetMachines(token: string): Promise<AdminMachine[]> {
  return authFetch('/admin/machines', token)
}

export function adminSetStatus(token: string, machineId: number, status: MachineStatus): Promise<AdminMachine> {
  return authFetch(`/admin/machines/${machineId}`, token, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
}

export function adminGetPowerHistory(token: string, machineId: number, hours = 24): Promise<PowerDataPoint[]> {
  return authFetch(`/admin/machines/${machineId}/power-history?hours=${hours}`, token)
}

export function adminGetSettings(token: string): Promise<AdminSettings> {
  return authFetch('/admin/settings', token)
}
