import { MachineDetail, MachinesResponse } from '../types/machine'
import { authFetch } from './client'

export interface MachineRequestResponse {
  assigned_machine: MachineDetail
  reserved_until: string
}

export interface MyReservationResponse {
  active: boolean
  assigned_machine?: MachineDetail
  reserved_until?: string
}

export function getMachines(token: string): Promise<MachinesResponse> {
  return authFetch('/machines', token)
}

export function requestMachine(token: string): Promise<MachineRequestResponse> {
  return authFetch('/machines/request', token, { method: 'POST' })
}

export function getMyReservation(token: string): Promise<MyReservationResponse> {
  return authFetch('/machines/my-reservation', token)
}
