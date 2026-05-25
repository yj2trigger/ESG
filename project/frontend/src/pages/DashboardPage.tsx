import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useMachineStore } from '../store/machineStore'
import { getMachines, requestMachine, MachineRequestResponse } from '../api/machines'
import { joinQueue, leaveQueue, getQueueStatus, QueueJoinResponse } from '../api/queue'
import { useWebSocket, WsMessage } from '../hooks/useWebSocket'
import { MachineMode, FloorSummary, MachineDetail } from '../types/machine'

const GENDER_LABEL: Record<string, string> = { male: '남성', female: '여성' }

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const { data, loading, error, setData, setLoading, setError } = useMachineStore()
  const [queueAlert, setQueueAlert] = useState<{ machine: MachineDetail; reserved_until: string } | null>(null)
  const [modeBResult, setModeBResult] = useState<MachineRequestResponse | null>(null)

  const [liveQueuePos, setLiveQueuePos] = useState<number | null>(null)
  const [liveQueueTotal, setLiveQueueTotal] = useState<number | null>(null)

  const token = user?.token ?? null

  const refresh = async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await getMachines(token)
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류 발생')
    }
  }

  useWebSocket(token, (msg: WsMessage) => {
    if (msg.type === 'machines_updated') {
      refresh()
    } else if (msg.type === 'queue_notify' && msg.machine && msg.reserved_until) {
      setQueueAlert({ machine: msg.machine as MachineDetail, reserved_until: msg.reserved_until })
    } else if (msg.type === 'queue_position_updated' && msg.position != null) {
      setLiveQueuePos(msg.position as number)
      setLiveQueueTotal(msg.total as number)
    }
  })

  useEffect(() => {
    refresh()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (loading && !data) return <Screen><p>불러오는 중...</p></Screen>
  if (error && !data) return <Screen><p style={{ color: '#c00' }}>{error}</p><button style={styles.refreshBtn} onClick={refresh}>다시 시도</button></Screen>
  if (!data) return null

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <span style={styles.headerTitle}>세탁기 현황</span>
        <span style={styles.userInfo}>
          {user?.username} ({GENDER_LABEL[user?.gender ?? '']})
        </span>
        {user?.role === 'admin' && (
          <button style={styles.adminBtn} onClick={() => navigate('/admin')}>관리</button>
        )}
        <button style={styles.settingsBtn} onClick={() => navigate('/settings')}>설정</button>
      </header>

      <main style={styles.main}>
        {queueAlert && (
          <div style={styles.queueAlert}>
            <strong>세탁기가 배정되었습니다!</strong>
            <span>{queueAlert.machine.floor}층 {queueAlert.machine.machine_number}번</span>
            <span style={{ fontSize: '0.8rem', color: '#555' }}>
              {new Date(queueAlert.reserved_until).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}까지 10분 소프트 예약
            </span>
            <button style={styles.alertClose} onClick={() => setQueueAlert(null)}>확인</button>
          </div>
        )}

        {modeBResult && (
          <div style={styles.queueAlert}>
            <strong>세탁기가 배정되었습니다!</strong>
            <span>{modeBResult.assigned_machine.floor}층 {modeBResult.assigned_machine.machine_number}번</span>
            <span style={{ fontSize: '0.8rem', color: '#555' }}>
              {new Date(modeBResult.reserved_until).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}까지 10분 소프트 예약 (미사용 시 자동 해제)
            </span>
            <button style={styles.alertClose} onClick={() => setModeBResult(null)}>확인</button>
          </div>
        )}

        <ModeBanner mode={data.mode} />

        {data.mode === 'A' && <ModeAView floors={data.floors} />}
        {data.mode === 'B' && !modeBResult && (
          <ModeBView token={user?.token ?? ''} onAssigned={(res) => { setModeBResult(res); refresh() }} />
        )}
        {data.mode === 'C' && (
          <ModeCView
            token={user?.token ?? ''}
            onDone={refresh}
            livePosition={liveQueuePos}
            liveTotal={liveQueueTotal}
          />
        )}

        <button style={styles.refreshBtn} onClick={refresh}>새로고침</button>
      </main>
    </div>
  )
}

// ── ModeBanner ───────────────────────────────────────────────

function ModeBanner({ mode }: { mode: MachineMode }) {
  const info: Record<MachineMode, { label: string; color: string; desc: string }> = {
    A: { label: 'MODE A', color: '#2a7', desc: '이용 가능 세탁기 4대 이상 — 층별 현황을 직접 확인하세요' },
    B: { label: 'MODE B', color: '#e80', desc: '이용 가능 세탁기 1~3대 — 수요 분산을 위해 위치를 직접 안내합니다' },
    C: { label: 'MODE C', color: '#c33', desc: '이용 가능 세탁기 없음 — 대기열에 등록하시면 자리가 나면 알림을 드립니다' },
  }
  const { label, color, desc } = info[mode]
  return (
    <div style={{ ...styles.modeBanner, borderColor: color }}>
      <span style={{ ...styles.modeLabel, color }}>{label}</span>
      <p style={styles.modeDesc}>{desc}</p>
    </div>
  )
}

// ── Mode A ───────────────────────────────────────────────────

function ModeAView({ floors }: { floors: FloorSummary[] }) {
  return (
    <div style={styles.floorGrid}>
      {floors.map((f) => (
        <div key={f.floor} style={styles.floorCard}>
          <div style={styles.floorNum}>{f.floor}층</div>
          <div style={styles.floorCount}>{f.available_count}대</div>
          <div style={styles.floorLabel}>이용 가능</div>
        </div>
      ))}
    </div>
  )
}

// ── Mode B ───────────────────────────────────────────────────

function ModeBView({ token, onAssigned }: { token: string; onAssigned: (res: MachineRequestResponse) => void }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleRequest = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await requestMachine(token)
      onAssigned(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류 발생')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.actionBox}>
      <p style={styles.actionDesc}>세탁기 1대를 배정해드립니다 (10분 소프트 예약)</p>
      {error && <p style={styles.errorText}>{error}</p>}
      <button style={styles.actionBtn} onClick={handleRequest} disabled={loading}>
        {loading ? '배정 중...' : '사용하시겠습니까?'}
      </button>
      <p style={styles.actionNote}>버튼을 누르면 해당 층과 번호를 안내합니다</p>
    </div>
  )
}

// ── Mode C ───────────────────────────────────────────────────

function ModeCView({
  token,
  onDone,
  livePosition,
  liveTotal,
}: {
  token: string
  onDone: () => void
  livePosition: number | null
  liveTotal: number | null
}) {
  const [queueInfo, setQueueInfo] = useState<QueueJoinResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getQueueStatus(token).then((status) => {
      if (status.in_queue && status.queue_position != null && status.total != null) {
        setQueueInfo({ queue_position: status.queue_position, total: status.total, message: '' })
      }
    }).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleJoin = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await joinQueue(token)
      setQueueInfo(res)
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류 발생')
    } finally {
      setLoading(false)
    }
  }

  const handleLeave = async () => {
    setLoading(true)
    setError(null)
    try {
      await leaveQueue(token)
      setQueueInfo(null)
      onDone()
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류 발생')
    } finally {
      setLoading(false)
    }
  }

  if (queueInfo) {
    const displayPos = livePosition ?? queueInfo.queue_position
    const displayTotal = liveTotal ?? queueInfo.total
    return (
      <div style={styles.resultBox}>
        <p style={styles.resultTitle}>대기열에 등록되었습니다</p>
        <p style={styles.resultBig}>현재 {displayPos}번째</p>
        <p style={{ ...styles.resultNote, fontSize: '0.85rem', color: '#666' }}>
          전체 대기 {displayTotal}명
        </p>
        <p style={styles.resultNote}>자리가 나면 알림을 드립니다 (10분 내 미사용 시 다음 순서로)</p>
        <button style={{ ...styles.actionBtn, background: '#888', marginTop: '1rem' }} onClick={handleLeave} disabled={loading}>
          {loading ? '취소 중...' : '대기 취소'}
        </button>
      </div>
    )
  }

  return (
    <div style={styles.actionBox}>
      <p style={styles.actionDesc}>현재 이용 가능한 세탁기가 없습니다</p>
      {error && <p style={styles.errorText}>{error}</p>}
      <button style={styles.actionBtn} onClick={handleJoin} disabled={loading}>
        {loading ? '등록 중...' : '대기열 등록'}
      </button>
      <p style={styles.actionNote}>자리가 나면 알림을 드립니다 (10분 내 미사용 시 다음 순서로 넘어감)</p>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────

function Screen({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'sans-serif' }}>
      {children}
    </div>
  )
}

// ── styles ───────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'sans-serif' },
  header: { display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.75rem 1.5rem', borderBottom: '1px solid #eee', background: '#fff' },
  headerTitle: { fontWeight: 700, fontSize: '1.1rem', flex: 1 },
  userInfo: { fontSize: '0.875rem', color: '#555' },
  settingsBtn: { padding: '0.35rem 0.85rem', fontSize: '0.8rem', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', background: '#fff' },
  adminBtn: { padding: '0.35rem 0.85rem', fontSize: '0.8rem', border: '1px solid #555', borderRadius: '4px', cursor: 'pointer', background: '#333', color: '#fff' },
  main: { flex: 1, padding: '1.5rem', maxWidth: '600px', margin: '0 auto', width: '100%', boxSizing: 'border-box' },
  modeBanner: { border: '2px solid', borderRadius: '10px', padding: '1rem 1.25rem', marginBottom: '1.5rem' },
  modeLabel: { fontWeight: 800, fontSize: '1.1rem' },
  modeDesc: { margin: '0.4rem 0 0', fontSize: '0.9rem', color: '#444' },
  floorGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: '0.75rem' },
  floorCard: { border: '1px solid #ddd', borderRadius: '8px', padding: '1rem', textAlign: 'center' },
  floorNum: { fontWeight: 700, fontSize: '1rem' },
  floorCount: { fontSize: '1.75rem', fontWeight: 800, color: '#2a7', margin: '0.25rem 0' },
  floorLabel: { fontSize: '0.75rem', color: '#777' },
  actionBox: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem', padding: '2rem', border: '1px solid #ddd', borderRadius: '10px' },
  actionDesc: { margin: 0, fontSize: '0.95rem', textAlign: 'center' },
  actionBtn: { padding: '0.875rem 2.5rem', fontSize: '1rem', fontWeight: 700, background: '#333', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer' },
  actionNote: { margin: 0, fontSize: '0.8rem', color: '#888', textAlign: 'center' },
  resultBox: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', padding: '2rem', border: '2px solid #2a7', borderRadius: '10px', textAlign: 'center' },
  resultTitle: { margin: 0, fontSize: '0.95rem', color: '#555' },
  resultBig: { margin: 0, fontSize: '2rem', fontWeight: 800, color: '#333' },
  resultNote: { margin: 0, fontSize: '0.8rem', color: '#888' },
  errorText: { color: '#c00', fontSize: '0.875rem', margin: 0 },
  refreshBtn: { marginTop: '1.5rem', display: 'block', padding: '0.5rem 1.5rem', fontSize: '0.875rem', border: '1px solid #ccc', borderRadius: '6px', cursor: 'pointer', background: '#fff' },
  queueAlert: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', padding: '1rem 1.5rem', marginBottom: '1rem', background: '#e8f5e9', border: '2px solid #2a7', borderRadius: '10px', textAlign: 'center' },
  alertClose: { marginTop: '0.5rem', padding: '0.4rem 1.5rem', fontSize: '0.875rem', fontWeight: 600, background: '#2a7', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' },
}