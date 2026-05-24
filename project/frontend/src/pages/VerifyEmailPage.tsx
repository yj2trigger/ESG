import { useState, FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { verifyEmail } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import { AuthUser, Gender } from '../types/user'

export default function VerifyEmailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const email = searchParams.get('email') ?? ''
  const setUser = useAuthStore((s) => s.setUser)

  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await verifyEmail(email, code)
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
      <h1 style={styles.title}>이메일 인증</h1>
      <p style={styles.desc}>
        <strong>{email}</strong>로 발송된<br />6자리 인증 코드를 입력하세요.
      </p>

      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          style={styles.input}
          placeholder="인증 코드 6자리"
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
          maxLength={6}
          required
          autoComplete="one-time-code"
          inputMode="numeric"
        />

        {error && <p style={styles.error}>{error}</p>}

        <button style={styles.submit} type="submit" disabled={loading || code.length !== 6}>
          {loading ? '확인 중...' : '인증 완료'}
        </button>

        <button
          style={styles.back}
          type="button"
          onClick={() => navigate('/login', { replace: true })}
        >
          로그인 화면으로 돌아가기
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
  desc: {
    textAlign: 'center',
    color: '#555',
    lineHeight: 1.6,
    margin: 0,
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
    width: '300px',
  },
  input: {
    padding: '0.75rem 1rem',
    fontSize: '1.5rem',
    textAlign: 'center',
    letterSpacing: '0.5rem',
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
  back: {
    padding: '0.5rem',
    fontSize: '0.875rem',
    color: '#777',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    textDecoration: 'underline',
  },
  error: {
    color: '#c00',
    fontSize: '0.875rem',
    margin: 0,
    textAlign: 'center',
  },
}
