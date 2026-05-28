import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { useMachineStore } from '../store/machineStore'
import { getMachines, requestMachine, getMyReservation, MachineRequestResponse } from '../api/machines'
import { joinQueue, leaveQueue, getQueueStatus, acceptQueueOffer, QueueJoinResponse } from '../api/queue'
import { useWebSocket, WsMessage } from '../hooks/useWebSocket'
import { MachineMode, FloorSummary, MachineDetail } from '../types/machine'

const GENDER_LABEL: Record<string, string> = { male: '남성', female: '여성' }

function asUtc(s: string): Date {
  return new Date(s.endsWith('Z') || s.includes('+') ? s : s + 'Z')
}

interface PendingOffer {
  machine: MachineDetail
  accept_until: string
}

interface ActiveReservation {
  machine: MachineDetail
  reserved_until: string
}

export interface PollTick {
  at: number
  intervalSec: number
  fastIntervalSec: number
  slowIntervalSec: number
  priorityCount: number
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const { data, loading, error, setData, setLoading, setError } = useMachineStore()

  const [pendingOffer, setPendingOffer] = useState<PendingOffer | null>(null)
  const [activeReservation, setActiveReservation] = useState<ActiveReservation | null>(null)
  const [queueInfo, setQueueInfo] = useState<QueueJoinResponse | null>(null)
  const [liveQueuePos, setLiveQueuePos] = useState<number | null>(null)
  const [liveQueueTotal, setLiveQueueTotal] = useState<number | null>(null)
  const [machineStartedToast, setMachineStartedToast] = useState<{ floor: number; machine_number: number } | null>(null)
  const [pollTick, setPollTick] = useState<PollTick | null>(null)

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
    } else if (msg.type === 'queue_offer' && msg.machine && msg.accept_until) {
      setPendingOffer({ machine: msg.machine as MachineDetail, accept_until: msg.accept_until })
      setQueueInfo(null)
    } else if (msg.type === 'queue_offer_expired') {
      setPendingOffer(null)
      if (token) {
        getQueueStatus(token).then((status) => {
          if (status.in_queue && status.queue_position != null && status.total != null) {
            setQueueInfo({ queue_position: status.queue_position, total: status.total, message: '' })
          }
        }).catch(() => {})
      }
    } else if (msg.type === 'queue_position_updated' && msg.position != null) {
      setLiveQueuePos(msg.position as number)
      setLiveQueueTotal(msg.total as number)
    } else if (msg.type === 'machine_started' && msg.machine) {
      setMachineStartedToast({ floor: msg.machine.floor, machine_number: msg.machine.machine_number })
      setActiveReservation(null)
    } else if (msg.type === 'poll_tick' && msg.next_interval_sec) {
      setPollTick({
        at: Date.now(),
        intervalSec: msg.next_interval_sec,
        fastIntervalSec: msg.fast_interval_sec ?? msg.next_interval_sec,
        slowIntervalSec: msg.slow_interval_sec ?? msg.next_interval_sec,
        priorityCount: msg.priority_count ?? 0,
      })
    }
  })

  useEffect(() => {
    refresh()
    if (!token) return
    Promise.all([getMyReservation(token), getQueueStatus(token)]).then(([res, status]) => {
      if (status.in_queue && status.is_notified && status.accept_until && res.active && res.assigned_machine) {
        setPendingOffer({ machine: res.assigned_machine, accept_until: status.accept_until })
      } else if (res.active && res.assigned_machine && res.reserved_until) {
        setActiveReservation({ machine: res.assigned_machine, reserved_until: res.reserved_until })
      } else if (status.in_queue && status.queue_position != null && status.total != null) {
        setQueueInfo({ queue_position: status.queue_position, total: status.total, message: '' })
      }
    }).catch(() => {})
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    if (!activeReservation) return
    const ms = asUtc(activeReservation.reserved_until).getTime() - Date.now()
    if (ms <= 0) { setActiveReservation(null); return }
    const t = setTimeout(() => setActiveReservation(null), ms)
    return () => clearTimeout(t)
  }, [activeReservation])

  if (loading && !data) return <Screen><p>불러오는 중...</p></Screen>
  if (error && !data) return <Screen><p style={{ color: '#c00' }}>{error}</p><button style={styles.refreshBtn} onClick={refresh}>다시 시도</button></Screen>
  if (!data) return null

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <span style={styles.headerTitle}>세탁기 현황</span>
        <span style={styles.userInfo}>{user?.username} ({GENDER_LABEL[user?.gender ?? '']})</span>
        {user?.role === 'admin' && (
          <button style={styles.adminBtn} onClick={() => navigate('/admin')}>관리</button>
        )}
        <button style={styles.settingsBtn} onClick={() => navigate('/settings')}>설정</button>
      </header>

      <main style={styles.main}>
        {machineStartedToast && (
          <MachineStartedToast machine={machineStartedToast} onDismiss={() => setMachineStartedToast(null)} />
        )}
        {pendingOffer && (
          <PendingOfferBanner
            offer={pendingOffer}
            token={token ?? ''}
            onAccepted={(res) => {
              setPendingOffer(null)
              setActiveReservation({ machine: res.assigned_machine, reserved_until: res.reserved_until })
              refresh()
            }}
            onExpired={() => setPendingOffer(null)}
          />
        )}
        {activeReservation && <ActiveReservationBanner reservation={activeReservation} />}

        <ModeBanner mode={data.mode} />
        <PollingInfoBar pollTick={pollTick} />

        {data.mode === 'A' && !queueInfo && !pendingOffer && <ModeAView floors={data.floors} />}
        {data.mode === 'B' && !activeReservation && !queueInfo && !pendingOffer && (
          <ModeBView
            token={user?.token ?? ''}
            onAssigned={(res) => {
              setActiveReservation({ machine: res.assigned_machine, reserved_until: res.reserved_until })
              refresh()
            }}
          />
        )}
        {(data.mode === 'C' || queueInfo) && !pendingOffer && (
          <ModeCView
            token={user?.token ?? ''}
            username={user?.username ?? ''}
            onDone={refresh}
            livePosition={liveQueuePos}
            liveTotal={liveQueueTotal}
            queueInfo={queueInfo}
            setQueueInfo={setQueueInfo}
          />
        )}

        <button style={styles.refreshBtn} onClick={refresh}>새로고침</button>
      </main>
    </div>
  )
}

// ── MachineStartedToast ──────────────────────────────────────

function MachineStartedToast({ machine, onDismiss }: { machine: { floor: number; machine_number: number }; onDismiss: () => void }) {
  const [secsLeft, setSecsLeft] = useState(10)
  useEffect(() => {
    const interval = setInterval(() => {
      setSecsLeft((s) => {
        if (s <= 1) { clearInterval(interval); onDismiss(); return 0 }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [onDismiss])
  return (
    <div style={styles.machineStartedToast}>
      <div style={styles.toastProgressTrack}>
        <div style={{ ...styles.toastProgressBar, width: `${(secsLeft / 10) * 100}%` }} />
      </div>
      <strong style={{ fontSize: '1.05rem' }}>세탁기 작동이 시작되었습니다</strong>
      <span style={{ fontSize: '0.9rem', color: '#444' }}>{machine.floor}층 {machine.machine_number}번 세탁기</span>
      <span style={{ fontSize: '0.75rem', color: '#888' }}>{secsLeft}초 후 사라집니다</span>
    </div>
  )
}

// ── PollingInfoBar ───────────────────────────────────────────

function PollingInfoBar({ pollTick }: { pollTick: PollTick | null }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  if (!pollTick) {
    return (
      <div style={styles.pollingBar}>
        <span>IoT 감지 주기: 동기화 대기 중…</span>
      </div>
    )
  }

  const { at, intervalSec, fastIntervalSec, slowIntervalSec, priorityCount } = pollTick
  const elapsed = Math.floor((now - at) / 1000)
  const remaining = Math.max(0, intervalSec - elapsed)
  const nextText = remaining <= 3 ? '잠시 후' : `${remaining}초 후`

  return (
    <div style={styles.pollingBar}>
      <span>세탁기 정보 반영: {nextText} 갱신 예정 · 실제 변경 시에만 적용</span>
      <span>IoT 감지 주기: 우선 기기({priorityCount}대) {fastIntervalSec}초 · 일반 기기 {slowIntervalSec}초</span>
    </div>
  )
}

// ── PendingOfferBanner ────────────────────────────────────────

function PendingOfferBanner({ offer, token, onAccepted, onExpired }: {
  offer: PendingOffer; token: string
  onAccepted: (res: MachineRequestResponse) => void; onExpired: () => void
}) {
  const [secsLeft, setSecsLeft] = useState(() => Math.max(0, Math.floor((asUtc(offer.accept_until).getTime() - Date.now()) / 1000)))
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const expiredRef = useRef(false)

  useEffect(() => {
    const interval = setInterval(() => {
      const secs = Math.max(0, Math.floor((asUtc(offer.accept_until).getTime() - Date.now()) / 1000))
      setSecsLeft(secs)
      if (secs === 0 && !expiredRef.current) { expiredRef.current = true; clearInterval(interval); onExpired() }
    }, 500)
    return () => clearInterval(interval)
  }, [offer.accept_until, onExpired])

  const handleAccept = async () => {
    setLoading(true); setError(null)
    try { onAccepted(await acceptQueueOffer(token)) }
    catch (e) { setError(e instanceof Error ? e.message : '수락 실패'); setLoading(false) }
  }

  const mins = Math.floor(secsLeft / 60), secs = secsLeft % 60
  return (
    <div style={styles.offerBanner}>
      <strong style={{ fontSize: '1.05rem' }}>세탁기 배정 알림!</strong>
      <span style={styles.offerMachine}>{offer.machine.floor}층 {offer.machine.machine_number}번</span>
      <span style={styles.offerTimer}>수락 가능 시간 {mins}:{String(secs).padStart(2, '0')} 남음</span>
      <p style={{ ...styles.actionNote, color: '#c60' }}>5분 이내로 수락하셔야 합니다. 시간이 지나면 대기열 맨 뒤로 이동됩니다.</p>
      {error && <p style={styles.errorText}>{error}</p>}
      <button style={{ ...styles.actionBtn, background: '#2a7' }} onClick={handleAccept} disabled={loading || secsLeft === 0}>
        {loading ? '수락 중...' : '수락하기'}
      </button>
    </div>
  )
}

// ── ActiveReservationBanner ───────────────────────────────────

function ActiveReservationBanner({ reservation }: { reservation: ActiveReservation }) {
  const [secsLeft, setSecsLeft] = useState(() => Math.max(0, Math.floor((asUtc(reservation.reserved_until).getTime() - Date.now()) / 1000)))
  useEffect(() => {
    const interval = setInterval(() => setSecsLeft(Math.max(0, Math.floor((asUtc(reservation.reserved_until).getTime() - Date.now()) / 1000))), 1000)
    return () => clearInterval(interval)
  }, [reservation.reserved_until])
  const mins = Math.floor(secsLeft / 60), secs = secsLeft % 60
  return (
    <div style={styles.reservationBanner}>
      <strong>세탁기가 배정되었습니다!</strong>
      <span style={styles.offerMachine}>{reservation.machine.floor}층 {reservation.machine.machine_number}번</span>
      <span style={styles.offerTimer}>예약 유효 시간 {mins}:{String(secs).padStart(2, '0')} 남음</span>
      <p style={styles.actionNote}>위 시간 이내에 세탁기를 사용해주세요.<br />시간이 지나면 예약이 자동으로 해제됩니다.</p>
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
    setLoading(true); setError(null)
    try { onAssigned(await requestMachine(token)) }
    catch (e) { setError(e instanceof Error ? e.message : '오류 발생') }
    finally { setLoading(false) }
  }
  return (
    <div style={styles.actionBox}>
      <p style={styles.actionDesc}>지금 바로 세탁기를 배정받으실 수 있습니다</p>
      {error && <p style={styles.errorText}>{error}</p>}
      <button style={styles.actionBtn} onClick={handleRequest} disabled={loading}>
        {loading ? '배정 중...' : '배정받기'}
      </button>
      <p style={styles.actionNote}>배정 후 10분 이내에 세탁기를 찾아가셔야 합니다.<br />시간이 지나면 자동으로 해제됩니다.</p>
    </div>
  )
}

// ── Mode C ───────────────────────────────────────────────────

function ModeCView({ token, username, onDone, livePosition, liveTotal, queueInfo, setQueueInfo }: {
  token: string; username: string; onDone: () => void
  livePosition: number | null; liveTotal: number | null
  queueInfo: QueueJoinResponse | null; setQueueInfo: (v: QueueJoinResponse | null) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleJoin = async () => {
    setLoading(true); setError(null)
    try { setQueueInfo(await joinQueue(token)); onDone() }
    catch (e) { setError(e instanceof Error ? e.message : '오류 발생') }
    finally { setLoading(false) }
  }
  const handleLeave = async () => {
    setLoading(true); setError(null)
    try { await leaveQueue(token); setQueueInfo(null); onDone() }
    catch (e) { setError(e instanceof Error ? e.message : '오류 발생') }
    finally { setLoading(false) }
  }

  if (queueInfo) {
    return (
      <div style={styles.resultBox}>
        <p style={styles.resultTitle}>대기열에 등록되었습니다</p>
        <p style={styles.resultBig}>현재 {livePosition ?? queueInfo.queue_position}번째</p>
        <p style={{ ...styles.resultNote, fontSize: '0.85rem', color: '#666' }}>전체 대기 {liveTotal ?? queueInfo.total}명</p>
        <p style={styles.resultNote}>세탁기가 비면 배정 알림이 옵니다.<br />알림 수신 후 5분 이내로 수락하셔야 합니다.</p>
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
      <p style={styles.actionNote}>세탁기가 비면 배정 알림이 옵니다.<br />알림 수신 후 5분 이내로 수락하시면<br />10분동안 <strong>{username}</strong>님에게만 이용 가능하다고 표시됩니다.</p>
    </div>
  )
}

// ── helpers ──────────────────────────────────────────────────

function Screen({ children }: { children: React.ReactNode }) {
  return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'sans-serif' }}>{children}</div>
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
  modeBanner: { border: '2px solid', borderRadius: '10px', padding: '1rem 1.25rem', marginBottom: '0.5rem' },
  modeLabel: { fontWeight: 800, fontSize: '1.1rem' },
  modeDesc: { margin: '0.4rem 0 0', fontSize: '0.9rem', color: '#444' },
  pollingBar: { display: 'flex', flexDirection: 'column', gap: '0.15rem', padding: '0.4rem 0.75rem', marginBottom: '1rem', background: '#f8f9fa', borderRadius: '6px', fontSize: '0.72rem', color: '#999' },
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
  offerBanner: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', padding: '1.25rem 1.5rem', marginBottom: '1rem', background: '#fff8e1', border: '2px solid #e80', borderRadius: '10px', textAlign: 'center' },
  reservationBanner: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.4rem', padding: '1.25rem 1.5rem', marginBottom: '1rem', background: '#e8f5e9', border: '2px solid #2a7', borderRadius: '10px', textAlign: 'center' },
  offerMachine: { fontSize: '1.5rem', fontWeight: 800, color: '#333' },
  offerTimer: { fontSize: '1rem', fontWeight: 700, color: '#555' },
  machineStartedToast: { position: 'relative', overflow: 'hidden', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.3rem', padding: '1rem 1.5rem', marginBottom: '1rem', background: '#e8f5e9', border: '2px solid #2a7', borderRadius: '10px', textAlign: 'center' },
  toastProgressTrack: { position: 'absolute', top: 0, left: 0, right: 0, height: '3px', background: '#c8e6c9' },
  toastProgressBar: { height: '3px', background: '#2a7', transition: 'width 1s linear' },
}
