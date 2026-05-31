import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useAuthStore } from '../store/authStore'
import { useWebSocket, WsMessage } from '../hooks/useWebSocket'
import { adminGetMachines, adminSetStatus, adminGetPowerHistory, adminGetSettings, AdminMachine, MachineStatus, PowerDataPoint } from '../api/admin'

const STATUS_LABEL: Record<MachineStatus, string> = {
  available: '이용 가능',
  in_use: '사용 중',
  soft_reserved: '소프트 예약',
  broken: '고장',
}

const STATUS_COLOR: Record<MachineStatus, string> = {
  available: '#2a7',
  in_use: '#c33',
  soft_reserved: '#e80',
  broken: '#888',
}

const GENDER_LABEL: Record<string, string> = { male: '남', female: '여' }
const MANUAL_STATUSES: MachineStatus[] = ['available', 'in_use', 'broken']
const GRAPH_REFRESH_MS = 60_000
const STATUS_POLL_MS = 10_000
const MAX_HISTORY_DAYS = 30

function fmtHHMM(ts: number): string {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 현재 KST 날짜를 YYYY-MM-DD 문자열로 */
function todayKST(): string {
  const kst = new Date(Date.now() + 9 * 3600 * 1000)
  return kst.toISOString().slice(0, 10)
}

/** KST 날짜에 days 더함 */
function addDays(dateStr: string, days: number): string {
  const d = new Date(dateStr + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/** 30일 전 KST 날짜 */
function minDateKST(): string {
  return addDays(todayKST(), -MAX_HISTORY_DAYS)
}

function PowerGraph({
  machineId, token, startThreshold, stopThreshold,
}: {
  machineId: number; token: string; startThreshold: number; stopThreshold: number
}) {
  const [data, setData] = useState<PowerDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [lastFetched, setLastFetched] = useState<Date | null>(null)
  const [selectedDate, setSelectedDate] = useState(todayKST)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const today = todayKST()
  const isToday = selectedDate === today

  const fetchData = (date: string) => {
    adminGetPowerHistory(token, machineId, { date })
      .then((d) => { setData(d); setLastFetched(new Date()) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    setLoading(true)
    fetchData(selectedDate)
    if (intervalRef.current) clearInterval(intervalRef.current)
    // 오늘만 자동 갱신
    if (selectedDate === todayKST()) {
      intervalRef.current = setInterval(() => fetchData(selectedDate), GRAPH_REFRESH_MS)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machineId, token, selectedDate])

  const prevDay = () => setSelectedDate(d => addDays(d, -1))
  const nextDay = () => setSelectedDate(d => addDays(d, 1))

  const updatedLabel = lastFetched
    ? `${String(lastFetched.getHours()).padStart(2, '0')}:${String(lastFetched.getMinutes()).padStart(2, '0')}:${String(lastFetched.getSeconds()).padStart(2, '0')} 갱신`
    : ''

  // 선택된 KST 날짜의 00:00~23:59 범위 (ms)
  const domainStart = new Date(selectedDate + 'T00:00:00+09:00').getTime()
  const domainEnd   = new Date(selectedDate + 'T23:59:59+09:00').getTime()

  const chartData: { ts: number; power: number | null }[] = [
    { ts: domainStart, power: null },
    ...data.map(d => ({ ts: new Date(d.timestamp).getTime(), power: d.power_w })),
    { ts: domainEnd, power: null },
  ]

  const latest = data.length > 0 ? data[data.length - 1].power_w : null
  const isRunning = latest !== null && latest >= startThreshold

  const ticks: number[] = []
  for (let h = 0; h <= 21; h += 3) ticks.push(domainStart + h * 3600 * 1000)

  return (
    <div style={styles.graphContainer}>
      {/* 날짜 선택 키 */}
      <div style={styles.dateNav}>
        <button
          style={styles.navBtn}
          onClick={prevDay}
          disabled={selectedDate <= minDateKST()}
        >◀</button>
        <input
          type="date"
          value={selectedDate}
          min={minDateKST()}
          max={today}
          onChange={(e) => e.target.value && setSelectedDate(e.target.value)}
          style={styles.dateInput}
        />
        <button
          style={styles.navBtn}
          onClick={nextDay}
          disabled={isToday}
        >▶</button>
        {isToday && <span style={styles.todayBadge}>오늘</span>}
      </div>

      {/* 그래프 헤더 */}
      <div style={styles.graphHeader}>
        <span>현재 <strong>{latest !== null ? `${latest.toFixed(1)}W` : '— W'}</strong></span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ color: '#aaa', fontSize: '0.75rem' }}>{loading ? '로딩 중...' : updatedLabel}</span>
          <span style={{ color: latest === null ? '#888' : isRunning ? '#c33' : '#2a7', fontSize: '0.82rem' }}>
            {latest === null ? '● 데이터 없음' : isRunning ? '● 가동 중' : '● 정지'}
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <XAxis dataKey="ts" type="number" scale="time" domain={[domainStart, domainEnd]}
            ticks={ticks} tickFormatter={fmtHHMM} tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} unit="W" width={50} />
          <Tooltip
            labelFormatter={(v) => fmtHHMM(Number(v))}
            formatter={(v: unknown) => v !== null ? [`${Number(v).toFixed(1)}W`, '전력'] : ['—', '전력']}
          />
          <ReferenceLine y={startThreshold} stroke="#e80" strokeDasharray="4 2"
            label={{ value: `가동 ${startThreshold}W`, fontSize: 9, fill: '#e80', position: 'insideTopRight' }} />
          <ReferenceLine y={stopThreshold} stroke="#4a90d9" strokeDasharray="4 2"
            label={{ value: `정지 ${stopThreshold}W`, fontSize: 9, fill: '#4a90d9', position: 'insideBottomRight' }} />
          <Line type="monotone" dataKey="power" stroke="#4a90d9" dot={false} strokeWidth={1.5} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function AdminPage() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const [machines, setMachines] = useState<AdminMachine[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState<number | null>(null)
  const [expandedGraphs, setExpandedGraphs] = useState<Set<number>>(new Set())
  const [startThreshold, setStartThreshold] = useState(10)
  const [stopThreshold, setStopThreshold] = useState(5)

  const token = user?.token ?? null

  const reloadMachines = async () => {
    if (!user) return
    try { setMachines(await adminGetMachines(user.token)) } catch { /* silent */ }
  }

  useEffect(() => {
    if (!user || user.role !== 'admin') { navigate('/', { replace: true }); return }
    ;(async () => {
      setLoading(true)
      try {
        const [ms, cfg] = await Promise.all([adminGetMachines(user.token), adminGetSettings(user.token)])
        setMachines(ms)
        setStartThreshold(cfg.power_threshold_w)
        setStopThreshold(cfg.stop_threshold_w)
      } catch (e) {
        setError(e instanceof Error ? e.message : '오류 발생')
      } finally {
        setLoading(false)
      }
    })()
    const t = setInterval(reloadMachines, STATUS_POLL_MS)
    return () => clearInterval(t)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useWebSocket(token, (msg: WsMessage) => {
    if (msg.type === 'machines_updated') reloadMachines()
  })

  const handleStatusChange = async (machine: AdminMachine, status: MachineStatus) => {
    setUpdating(machine.id)
    try {
      const updated = await adminSetStatus(user!.token, machine.id, status)
      setMachines((prev) => prev.map((m) => m.id === updated.id ? updated : m))
    } catch (e) {
      alert(e instanceof Error ? e.message : '변경 실패')
    } finally {
      setUpdating(null)
    }
  }

  const toggleGraph = (machineId: number) => {
    setExpandedGraphs((prev) => {
      const next = new Set(prev)
      if (next.has(machineId)) next.delete(machineId)
      else next.add(machineId)
      return next
    })
  }

  if (loading) return <div style={styles.center}>불러오는 중...</div>
  if (error) return <div style={styles.center}><p style={{ color: '#c00' }}>{error}</p></div>

  const byFloor = machines.reduce<Record<number, AdminMachine[]>>((acc, m) => {
    acc[m.floor] = [...(acc[m.floor] ?? []), m]
    return acc
  }, {})

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <span style={styles.title}>관리자 — 세탁기 상태</span>
        <button style={styles.backBtn} onClick={() => navigate('/')}>← 대시보드</button>
      </header>
      <main style={styles.main}>
        <div style={styles.thresholdInfo}>
          가동 시작: <strong>{startThreshold}W</strong> · 정지 판단: <strong>{stopThreshold}W</strong>
          <span style={{ marginLeft: '0.75rem', color: '#bbb' }}>· {STATUS_POLL_MS / 1000}초 주기 + WS 실시간</span>
        </div>
        {Object.entries(byFloor).sort(([a], [b]) => Number(a) - Number(b)).map(([floor, ms]) => (
          <div key={floor} style={styles.floorSection}>
            <div style={styles.floorLabel}>{floor}층</div>
            {ms.map((m) => (
              <div key={m.id}>
                <div style={styles.machineRow}>
                  <div style={styles.machineInfo}>
                    <span style={{ fontWeight: 700 }}>{m.machine_number}번</span>
                    {m.gender_restriction && (
                      <span style={styles.genderTag}>{GENDER_LABEL[m.gender_restriction]}</span>
                    )}
                    <span style={{ ...styles.statusDot, color: STATUS_COLOR[m.status] }}>
                      ● {STATUS_LABEL[m.status]}
                    </span>
                  </div>
                  <div style={styles.btnGroup}>
                    <button style={styles.graphBtn} onClick={() => toggleGraph(m.id)}>
                      {expandedGraphs.has(m.id) ? '▲ 그래프' : '▼ 그래프'}
                    </button>
                    {MANUAL_STATUSES.filter((s) => s !== m.status).map((s) => (
                      <button
                        key={s}
                        style={{ ...styles.statusBtn, borderColor: STATUS_COLOR[s], color: STATUS_COLOR[s] }}
                        onClick={() => handleStatusChange(m, s)}
                        disabled={updating === m.id}
                      >{STATUS_LABEL[s]}</button>
                    ))}
                  </div>
                </div>
                {expandedGraphs.has(m.id) && (
                  <PowerGraph
                    machineId={m.id} token={user!.token}
                    startThreshold={startThreshold} stopThreshold={stopThreshold}
                  />
                )}
              </div>
            ))}
          </div>
        ))}
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', minHeight: '100vh', fontFamily: 'sans-serif' },
  center: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'sans-serif' },
  header: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1.5rem', borderBottom: '1px solid #eee', background: '#fff' },
  title: { fontWeight: 700, fontSize: '1.1rem' },
  backBtn: { padding: '0.35rem 0.85rem', fontSize: '0.85rem', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', background: '#fff' },
  main: { padding: '1rem', maxWidth: '640px', width: '100%', margin: '0 auto', boxSizing: 'border-box' },
  thresholdInfo: { fontSize: '0.78rem', color: '#888', marginBottom: '0.75rem', padding: '0.3rem 0.6rem', background: '#f8f9fa', borderRadius: '4px' },
  floorSection: { marginBottom: '1.25rem' },
  floorLabel: { fontWeight: 700, fontSize: '0.9rem', color: '#555', marginBottom: '0.5rem', paddingBottom: '0.25rem', borderBottom: '1px solid #eee' },
  machineRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', gap: '0.5rem', flexWrap: 'wrap' },
  machineInfo: { display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' },
  genderTag: { fontSize: '0.75rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: '#f0f0f0', color: '#555' },
  statusDot: { fontSize: '0.85rem' },
  btnGroup: { display: 'flex', gap: '0.4rem', flexWrap: 'wrap' },
  statusBtn: { padding: '0.25rem 0.6rem', fontSize: '0.78rem', border: '1px solid', borderRadius: '4px', cursor: 'pointer', background: '#fff', minWidth: '4.8rem', textAlign: 'center' },
  graphBtn: { padding: '0.25rem 0.6rem', fontSize: '0.78rem', border: '1px solid #4a90d9', borderRadius: '4px', cursor: 'pointer', background: '#fff', color: '#4a90d9' },
  graphContainer: { background: '#f8f9fa', borderRadius: '8px', padding: '0.75rem', marginBottom: '0.5rem', border: '1px solid #e9ecef' },
  dateNav: { display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.5rem' },
  navBtn: { padding: '0.2rem 0.5rem', fontSize: '0.8rem', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', background: '#fff', lineHeight: 1 },
  dateInput: { fontSize: '0.82rem', border: '1px solid #ccc', borderRadius: '4px', padding: '0.2rem 0.4rem', cursor: 'pointer', flex: 1, minWidth: 0 },
  todayBadge: { fontSize: '0.72rem', color: '#2a7', background: '#e8f5e9', padding: '0.1rem 0.4rem', borderRadius: '10px', whiteSpace: 'nowrap' },
  graphHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', fontSize: '0.85rem' },
}
