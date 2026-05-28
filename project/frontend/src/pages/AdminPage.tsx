import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useAuthStore } from '../store/authStore'
import { adminGetMachines, adminSetStatus, adminGetPowerHistory, AdminMachine, MachineStatus, PowerDataPoint } from '../api/admin'

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
const ALL_STATUSES: MachineStatus[] = ['available', 'in_use', 'broken']
const THRESHOLD_W = 100

function formatTime(iso: string): string {
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function PowerGraph({ machineId, token }: { machineId: number; token: string }) {
  const [data, setData] = useState<PowerDataPoint[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminGetPowerHistory(token, machineId, 24)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [machineId, token])

  if (loading) return <div style={styles.graphMsg}>불러오는 중...</div>
  if (data.length === 0) return <div style={styles.graphMsg}>데이터 없음 (polling 시작 후 수집됨)</div>

  const chartData = data.map((d) => ({ time: formatTime(d.timestamp), power: d.power_w }))
  const latest = data[data.length - 1]?.power_w ?? 0
  const isRunning = latest >= THRESHOLD_W

  return (
    <div style={styles.graphContainer}>
      <div style={styles.graphHeader}>
        <span>현재 <strong>{latest.toFixed(1)}W</strong></span>
        <span style={{ color: isRunning ? '#c33' : '#2a7', fontSize: '0.82rem' }}>
          {isRunning ? '● 가동 중' : '● 정지'}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
          <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} unit="W" width={50} />
          <Tooltip formatter={(v: unknown) => [`${Number(v).toFixed(1)}W`, '전력']} />
          <ReferenceLine
            y={THRESHOLD_W}
            stroke="#e80"
            strokeDasharray="4 2"
            label={{ value: '가동 기준', fontSize: 9, fill: '#e80', position: 'insideTopRight' }}
          />
          <Line type="monotone" dataKey="power" stroke="#4a90d9" dot={false} strokeWidth={1.5} />
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

  useEffect(() => {
    if (!user || user.role !== 'admin') {
      navigate('/', { replace: true })
      return
    }
    load()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      setMachines(await adminGetMachines(user!.token))
    } catch (e) {
      setError(e instanceof Error ? e.message : '오류 발생')
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (machine: AdminMachine, status: MachineStatus) => {
    setUpdating(machine.id)
    try {
      const updated = await adminSetStatus(user!.token, machine.id, status)
      setMachines((prev) => prev.map((m) => (m.id === updated.id ? updated : m)))
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
                    <button
                      style={styles.graphBtn}
                      onClick={() => toggleGraph(m.id)}
                    >
                      {expandedGraphs.has(m.id) ? '▲ 그래프' : '▼ 그래프'}
                    </button>
                    {ALL_STATUSES.filter((s) => s !== m.status).map((s) => (
                      <button
                        key={s}
                        style={{ ...styles.statusBtn, borderColor: STATUS_COLOR[s], color: STATUS_COLOR[s] }}
                        onClick={() => handleStatusChange(m, s)}
                        disabled={updating === m.id}
                      >
                        {STATUS_LABEL[s]}
                      </button>
                    ))}
                  </div>
                </div>
                {expandedGraphs.has(m.id) && (
                  <PowerGraph machineId={m.id} token={user!.token} />
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
  floorSection: { marginBottom: '1.25rem' },
  floorLabel: { fontWeight: 700, fontSize: '0.9rem', color: '#555', marginBottom: '0.5rem', paddingBottom: '0.25rem', borderBottom: '1px solid #eee' },
  machineRow: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', gap: '0.5rem', flexWrap: 'wrap' },
  machineInfo: { display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' },
  genderTag: { fontSize: '0.75rem', padding: '0.1rem 0.4rem', borderRadius: '4px', background: '#f0f0f0', color: '#555' },
  statusDot: { fontSize: '0.85rem' },
  btnGroup: { display: 'flex', gap: '0.4rem', flexWrap: 'wrap' },
  statusBtn: { padding: '0.25rem 0.6rem', fontSize: '0.78rem', border: '1px solid', borderRadius: '4px', cursor: 'pointer', background: '#fff' },
  graphBtn: { padding: '0.25rem 0.6rem', fontSize: '0.78rem', border: '1px solid #4a90d9', borderRadius: '4px', cursor: 'pointer', background: '#fff', color: '#4a90d9' },
  graphContainer: { background: '#f8f9fa', borderRadius: '8px', padding: '0.75rem', marginBottom: '0.5rem', border: '1px solid #e9ecef' },
  graphHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem', fontSize: '0.85rem' },
  graphMsg: { padding: '1rem', textAlign: 'center', color: '#888', fontSize: '0.85rem' },
}
