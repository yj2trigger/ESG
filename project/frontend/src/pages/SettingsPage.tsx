import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { changePassword, changeUsername } from '../api/auth'
import { AuthUser, Gender } from '../types/user'

export default function SettingsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)

  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNew, setPwNew] = useState('')
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [pwLoading, setPwLoading] = useState(false)

  const [unCurrent, setUnCurrent] = useState('')
  const [unNew, setUnNew] = useState('')
  const [unMsg, setUnMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [unLoading, setUnLoading] = useState(false)

  if (!user) return null

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault()
    setPwMsg(null)
    setPwLoading(true)
    try {
      await changePassword(user.token, pwCurrent, pwNew)
      setPwMsg({ ok: true, text: '비밀번호가 변경되었습니다' })
      setPwCurrent('')
      setPwNew('')
    } catch (err) {
      setPwMsg({ ok: false, text: err instanceof Error ? err.message : '오류가 발생했습니다' })
    } finally {
      setPwLoading(false)
    }
  }

  const handleChangeUsername = async (e: FormEvent) => {
    e.preventDefault()
    setUnMsg(null)
    setUnLoading(true)
    try {
      const res = await changeUsername(user.token, unCurrent, unNew)
      const updated: AuthUser = {
        token: res.access_token,
        username: res.username,
        gender: res.gender as Gender,
        role: res.role as 'user' | 'admin',
      }
      setUser(updated)
      setUnMsg({ ok: true, text: `사용자명이 "${res.username}"으로 변경되었습니다` })
      setUnCurrent('')
      setUnNew('')
    } catch (err) {
      setUnMsg({ ok: false, text: err instanceof Error ? err.message : '오류가 발생했습니다' })
    } finally {
      setUnLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate('/')}>← 돌아가기</button>
        <span style={styles.headerTitle}>계정 설정</span>
      </header>

      <main style={styles.main}>
        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>비밀번호 변경</h2>
          <form onSubmit={handleChangePassword} style={styles.form}>
            <input
              style={styles.input}
              type="password"
              placeholder="현재 비밀번호"
              value={pwCurrent}
              onChange={(e) => setPwCurrent(e.target.value)}
              required
              autoComplete="current-password"
            />
            <input
              style={styles.input}
              type="password"
              placeholder="새 비밀번호 (4자 이상)"
              value={pwNew}
              onChange={(e) => setPwNew(e.target.value)}
              required
              autoComplete="new-password"
            />
            {pwMsg && <p style={{ ...styles.msg, color: pwMsg.ok ? '#2a7' : '#c00' }}>{pwMsg.text}</p>}
            <button style={styles.btn} type="submit" disabled={pwLoading}>
              {pwLoading ? '변경 중...' : '비밀번호 변경'}
            </button>
          </form>
        </section>

        <hr style={styles.divider} />

        <section style={styles.section}>
          <h2 style={styles.sectionTitle}>사용자명 변경</h2>
          <p style={styles.hint}>현재: <strong>{user.username}</strong></p>
          <form onSubmit={handleChangeUsername} style={styles.form}>
            <input
              style={styles.input}
              type="password"
              placeholder="현재 비밀번호"
              value={unCurrent}
              onChange={(e) => setUnCurrent(e.target.value)}
              required
              autoComplete="current-password"
            />
            <input
              style={styles.input}
              type="text"
              placeholder="새 사용자명 (2자 이상)"
              value={unNew}
              onChange={(e) => setUnNew(e.target.value)}
              required
              autoComplete="username"
            />
            {unMsg && <p style={{ ...styles.msg, color: unMsg.ok ? '#2a7' : '#c00' }}>{unMsg.text}</p>}
            <button style={styles.btn} type="submit" disabled={unLoading}>
              {unLoading ? '변경 중...' : '사용자명 변경'}
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', minHeight: '100vh', fontFamily: 'sans-serif' },
  header: { display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.75rem 1.5rem', borderBottom: '1px solid #eee', background: '#fff' },
  headerTitle: { fontWeight: 700, fontSize: '1.1rem' },
  backBtn: { padding: '0.35rem 0.85rem', fontSize: '0.8rem', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', background: '#fff' },
  main: { flex: 1, padding: '1.5rem', maxWidth: '420px', margin: '0 auto', width: '100%', boxSizing: 'border-box' },
  section: { display: 'flex', flexDirection: 'column', gap: '0.75rem' },
  sectionTitle: { margin: 0, fontSize: '1rem', fontWeight: 700 },
  form: { display: 'flex', flexDirection: 'column', gap: '0.65rem' },
  input: { padding: '0.75rem 1rem', fontSize: '1rem', border: '1px solid #ccc', borderRadius: '6px', outline: 'none' },
  btn: { padding: '0.875rem', fontSize: '1rem', fontWeight: 600, background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' },
  msg: { margin: 0, fontSize: '0.875rem', textAlign: 'center' },
  hint: { margin: 0, fontSize: '0.875rem', color: '#555' },
  divider: { border: 'none', borderTop: '1px solid #eee', margin: '1.5rem 0' },
}
