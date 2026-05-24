import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { AuthUser, Gender } from '../types/user'

type Tab = 'login' | 'register'

const GENDER_LABEL: Record<Gender, string> = { male: '남성', female: '여성' }

export default function LoginPage() {
  const navigate = useNavigate()
  const gender = useAuthStore((s) => s.gender)
  const setUser = useAuthStore((s) => s.setUser)

  const [tab, setTab] = useState<Tab>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = tab === 'register'
        ? await register(username, password, gender ?? 'male')
        : await login(username, password)

      const user: AuthUser = {
        token: res.access_token,
        username: res.username,
        gender: res.gender as Gender,
        role: res.role as 'user' | 'admin',
      }
      setUser(user)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : '오류가 발생했습니다')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>기숙사 세탁기 예약</h1>

      <div style={styles.tabs}>
        <button
          style={{ ...styles.tab, ...(tab === 'login' ? styles.tabActive : {}) }}
          onClick={() => setTab('login')}
        >
          로그인
        </button>
        <button
          style={{ ...styles.tab, ...(tab === 'register' ? styles.tabActive : {}) }}
          onClick={() => setTab('register')}
        >
          회원가입
        </button>
      </div>

      <form onSubmit={handleSubmit} style={styles.form}>
        {tab === 'register' && gender && (
          <div style={styles.genderBadge}>
            성별: <strong>{GENDER_LABEL[gender]}</strong>
          </div>
        )}

        <input
          style={styles.input}
          placeholder="사용자명"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
          autoComplete="username"
        />
        <input
          style={styles.input}
          type="password"
          placeholder="비밀번호"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete={tab === 'register' ? 'new-password' : 'current-password'}
        />

        {error && <p style={styles.error}>{error}</p>}

        <button style={styles.submit} type="submit" disabled={loading}>
          {loading ? '처리 중...' : tab === 'login' ? '로그인' : '회원가입'}
        </button>
      </form>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100vh',
    fontFamily: 'sans-serif',
    gap: '1.5rem',
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: 700,
    margin: 0,
  },
  tabs: {
    display: 'flex',
    border: '1px solid #ddd',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  tab: {
    padding: '0.6rem 2rem',
    fontSize: '0.95rem',
    border: 'none',
    background: '#f5f5f5',
    cursor: 'pointer',
    fontWeight: 500,
  },
  tabActive: {
    background: '#333',
    color: '#fff',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
    width: '300px',
  },
  genderBadge: {
    textAlign: 'center',
    fontSize: '0.9rem',
    color: '#555',
    padding: '0.4rem',
    background: '#f0f0f0',
    borderRadius: '6px',
  },
  input: {
    padding: '0.75rem 1rem',
    fontSize: '1rem',
    border: '1px solid #ccc',
    borderRadius: '6px',
    outline: 'none',
  },
  submit: {
    padding: '0.875rem',
    fontSize: '1rem',
    fontWeight: 600,
    background: '#333',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
  },
  error: {
    color: '#c00',
    fontSize: '0.875rem',
    margin: 0,
    textAlign: 'center',
  },
}