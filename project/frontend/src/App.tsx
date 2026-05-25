import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import GenderSelectPage from './pages/GenderSelectPage'
import LoginPage from './pages/LoginPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import DashboardPage from './pages/DashboardPage'
import AdminPage from './pages/AdminPage'
import SettingsPage from './pages/SettingsPage'

function SplashScreen() {
  const [phase, setPhase] = useState<'in' | 'hold' | 'out' | 'done'>('in')

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('hold'), 600)   // fade-in 완료
    const t2 = setTimeout(() => setPhase('out'), 2000)   // fade-out 시작
    const t3 = setTimeout(() => setPhase('done'), 3800)  // DOM 제거
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [])

  if (phase === 'done') return null

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      background: '#fff',
      opacity: phase === 'out' ? 0 : 1,
      transition: phase === 'in' ? 'opacity 0.6s ease' : 'opacity 1.8s ease',
      pointerEvents: 'none',
    }}>
      <p style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.5px', color: '#222' }}>
        ESG 세탁기 예약
      </p>
      <p style={{ margin: '0.75rem 0 0', fontSize: '0.95rem', color: '#666', textAlign: 'center', lineHeight: 1.6, padding: '0 2rem' }}>
        실시간 현황 정보를 제공하여<br />세탁기를 더 편리하게 이용할 수 있도록 돕습니다
      </p>
    </div>
  )
}

function App() {
  const user = useAuthStore((s) => s.user)
  const gender = useAuthStore((s) => s.gender)

  useEffect(() => {
    const requestFs = () => {
      const el = document.documentElement as HTMLElement & {
        webkitRequestFullscreen?: () => Promise<void>
      }
      const fn = el.requestFullscreen ?? el.webkitRequestFullscreen
      if (fn) fn.call(el).catch(() => {})
    }
    document.addEventListener('touchstart', requestFs, { once: true })
    return () => document.removeEventListener('touchstart', requestFs)
  }, [])

  return (
    <>
    <SplashScreen />
    <Routes>
      {/* 성별 선택 — 미로그인 + 성별 미선택 상태의 첫 진입점 */}
      <Route
        path="/gender"
        element={user ? <Navigate to="/" replace /> : <GenderSelectPage />}
      />

      {/* 로그인/회원가입 — 성별 선택 후 */}
      <Route
        path="/login"
        element={
          user
            ? <Navigate to="/" replace />
            : gender
              ? <LoginPage />
              : <Navigate to="/gender" replace />
        }
      />

      {/* 메인 — 로그인 필요 */}
      <Route
        path="/"
        element={
          user
            ? <DashboardPage />
            : <Navigate to={gender ? '/login' : '/gender'} replace />
        }
      />

      {/* 이메일 인증 — 회원가입 후 */}
      <Route
        path="/verify-email"
        element={user ? <Navigate to="/" replace /> : <VerifyEmailPage />}
      />

      <Route
        path="/admin"
        element={user?.role === 'admin' ? <AdminPage /> : <Navigate to="/" replace />}
      />

      <Route
        path="/settings"
        element={user ? <SettingsPage /> : <Navigate to={gender ? '/login' : '/gender'} replace />}
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </>
  )
}

export default App