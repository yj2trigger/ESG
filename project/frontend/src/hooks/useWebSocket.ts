import { useEffect, useRef } from 'react'

const WS_BASE = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000'

export interface WsMessage {
  type: 'machines_updated' | 'queue_offer' | 'queue_offer_expired' | 'queue_position_updated'
  mode?: string
  floors?: unknown[]
  machine?: { id: number; floor: number; machine_number: number }
  accept_until?: string
  message?: string
  position?: number
  total?: number
}

export function useWebSocket(token: string | null, onMessage: (msg: WsMessage) => void) {
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  useEffect(() => {
    if (!token) return

    let ws: WebSocket
    let retryTimer: ReturnType<typeof setTimeout>
    let active = true

    const connect = () => {
      ws = new WebSocket(`${WS_BASE}/ws?token=${encodeURIComponent(token)}`)

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data) as WsMessage
          onMessageRef.current(data)
        } catch {
          // ignore malformed messages
        }
      }

      ws.onclose = () => {
        if (active) {
          retryTimer = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      active = false
      clearTimeout(retryTimer)
      ws?.close()
    }
  }, [token])
}
