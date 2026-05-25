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
