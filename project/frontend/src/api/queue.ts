import { authFetch } from './client'
import type { MachineRequestResponse } from './machines'

export interface QueueJoinResponse {
  queue_position: number
  total: number
  message: string
}

export interface QueueLeaveResponse {
  message: string
}

export interface QueueStatusResponse {
  in_queue: boolean
  queue_position: number | null
  total: number | null
}

export function joinQueue(token: string): Promise<QueueJoinResponse> {
  return authFetch('/queue/join', token, { method: 'POST' })
}

export function leaveQueue(token: string): Promise<QueueLeaveResponse> {
  return authFetch('/queue/leave', token, { method: 'DELETE' })
}

export function getQueueStatus(token: string): Promise<QueueStatusResponse> {
  return authFetch('/queue/status', token)
}

export function acceptQueueOffer(token: string): Promise<MachineRequestResponse> {
  return authFetch('/queue/accept', token, { method: 'POST' })
}
