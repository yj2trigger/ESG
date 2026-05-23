import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import { Gender } from '../types/user'

export default function GenderSelectPage() {
  const setGender = useAuthStore((s) => s.setGender)
  const navigate = useNavigate()

  const handleSelect = (gender: Gender) => {
    setGender(gender)
    navigate('/', { replace: true })
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>성별을 선택해주세요</h1>
      <p style={styles.subtitle}>세탁기 현황 조회에 사용됩니다</p>
      <div style={styles.buttonGroup}>
        <button style={styles.button} onClick={() => handleSelect('male')}>
          남성
        </button>
        <button style={styles.button} onClick={() => handleSelect('female')}>
          여성
        </button>
      </div>
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
    gap: '1rem',
    fontFamily: 'sans-serif',
  },
  title: {
    fontSize: '1.75rem',
    fontWeight: 700,
    margin: 0,
  },
  subtitle: {
    color: '#666',
    margin: 0,
  },
  buttonGroup: {
    display: 'flex',
    gap: '1rem',
    marginTop: '1rem',
  },
  button: {
    padding: '0.875rem 2.5rem',
    fontSize: '1.1rem',
    fontWeight: 600,
    border: '2px solid #333',
    borderRadius: '8px',
    cursor: 'pointer',
    background: '#fff',
    transition: 'background 0.15s',
  },
}
