const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

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

export async function adminGetMachines(token: string): Promise<AdminMachine[]> {
  const res = await fetch(`${API_BASE}/admin/machines`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}

export async function adminSetStatus(
  token: string,
  machineId: number,
  status: MachineStatus,
): Promise<AdminMachine> {
  const res = await fetch(`${API_BASE}/admin/machines/${machineId}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail ?? '요청 실패')
  return data
}
