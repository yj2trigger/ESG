export type MachineMode = 'A' | 'B' | 'C'
export type MachineStatus = 'available' | 'in_use' | 'soft_reserved' | 'broken'

export interface FloorSummary {
  floor: number
  available_count: number
}

export interface MachineDetail {
  id: number
  floor: number
  machine_number: number
}

export interface MachinesResponse {
  mode: MachineMode
  floors: FloorSummary[]
  assigned_machine?: MachineDetail
  queue_position?: number
}