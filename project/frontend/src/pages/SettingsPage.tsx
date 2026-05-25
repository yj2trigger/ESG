import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { changePassword, changeUsername } from '../api/auth'
import { AuthUser, Gender } from '../types/user'

type ActiveSection = 'password' | 'username' | null

export default function SettingsPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const setUser = useAuthStore((s) => s.setUser)
  const logout = useAuthStore((s) => s.logout)

  const [active, setActive] = useState<ActiveSection>(null)

  const [pwCurrent, setPwCurrent] = useState('')
  const [pwNew, setPwNew] = useState('')
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [pwLoading, setPwLoading] = useState(false)

  const [unCurrent, setUnCurrent] = useState('')
  const [unNew, setUnNew] = useState('')
  const [unMsg, setUnMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [unLoading, setUnLoading] = useState(false)

  if (!user) return null

  const toggleSection = (section: ActiveSection) => {
    setActive((prev) => (prev === section ? null : section))
    setPwMsg(null)
    setUnMsg(null)
  }

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

  const handleLogout = () => {
    logout()
    navigate('/gender', { replace: true })
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <button style={styles.backBtn} onClick={() => navigate('/')}>← 돌아가기</button>
        <span style={styles.headerTitle}>계정 설정</span>
      </header>

      <main style={styles.main}>
        <p style={styles.userLabel}>{user.username}</p>

        <div style={styles.menuList}>
          <div style={styles.menuItem}>
            <button
              style={{ ...styles.menuBtn, ...(active === 'password' ? styles.menuBtnActive : {}) }}
              onClick={() => toggleSection('password')}
            >
              비밀번호 변경
              <span style={styles.chevron}>{active === 'password' ? '▲' : '▼'}</span>
            </button>
            {active === 'password' && (
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
                <button style={styles.submitBtn} type="submit" disabled={pwLoading}>
                  {pwLoading ? '변경 중...' : '확인'}
                </button>
              </form>
            )}
          </div>

          <div style={styles.menuItem}>
            <button
              style={{ ...styles.menuBtn, ...(active === 'username' ? styles.menuBtnActive : {}) }}
              onClick={() => toggleSection('username')}
            >
              아이디 변경
              <span style={styles.chevron}>{active === 'username' ? '▲' : '▼'}</span>
            </button>
            {active === 'username' && (
              <form onSubmit={handleChangeUsername} style={styles.form}>
                <p style={styles.hint}>현재 아이디: <strong>{user.username}</strong></p>
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
                  placeholder="새 아이디 (2자 이상)"
                  value={unNew}
                  onChange={(e) => setUnNew(e.target.value)}
                  required
                  autoComplete="username"
                />
                {unMsg && <p style={{ ...styles.msg, color: unMsg.ok ? '#2a7' : '#c00' }}>{unMsg.text}</p>}
                <button style={styles.submitBtn} type="submit" disabled={unLoading}>
                  {unLoading ? '변경 중...' : '확인'}
                </button>
              </form>
            )}
          </div>
        </div>

        <button style={styles.logoutBtn} onClick={handleLogout}>로그아웃</button>
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', minHeight: '100vh', fontFamily: 'sans-serif' },
  header: { display: 'flex', alignItems: 'center', gap: '1rem', padding: '0.75rem 1.5rem', borderBottom: '1px solid #eee', background: '#fff' },
  headerTitle: { fontWeight: 700, fontSize: '1.1rem' },
  backBtn: { padding: '0.35rem 0.85rem', fontSize: '0.8rem', border: '1px solid #ccc', borderRadius: '4px', cursor: 'pointer', background: '#fff' },
  main: { flex: 1, padding: '1.5rem', maxWidth: '420px', margin: '0 auto', width: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '1.25rem' },
  userLabel: { margin: 0, fontSize: '0.9rem', color: '#555' },
  menuList: { display: 'flex', flexDirection: 'column', border: '1px solid #ddd', borderRadius: '8px', overflow: 'hidden' },
  menuItem: { display: 'flex', flexDirection: 'column' },
  menuBtn: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', fontSize: '0.95rem', fontWeight: 500, background: '#fff', border: 'none', borderBottom: '1px solid #eee', cursor: 'pointer', textAlign: 'left' },
  menuBtnActive: { background: '#f8f8f8', fontWeight: 700 },
  chevron: { fontSize: '0.7rem', color: '#999' },
  form: { display: 'flex', flexDirection: 'column', gap: '0.65rem', padding: '1rem 1.25rem', background: '#fafafa', borderBottom: '1px solid #eee' },
  input: { padding: '0.75rem 1rem', fontSize: '1rem', border: '1px solid #ccc', borderRadius: '6px', outline: 'none', background: '#fff' },
  submitBtn: { padding: '0.75rem', fontSize: '0.95rem', fontWeight: 600, background: '#333', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' },
  msg: { margin: 0, fontSize: '0.875rem', textAlign: 'center' },
  hint: { margin: 0, fontSize: '0.85rem', color: '#555' },
  logoutBtn: { padding: '0.875rem', fontSize: '1rem', fontWeight: 600, background: '#fff', color: '#c00', border: '1px solid #fcc', borderRadius: '8px', cursor: 'pointer' },
}
