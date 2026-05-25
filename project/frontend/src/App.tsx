import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import GenderSelectPage from './pages/GenderSelectPage'
import LoginPage from './pages/LoginPage'
import VerifyEmailPage from './pages/VerifyEmailPage'
import DashboardPage from './pages/DashboardPage'
import AdminPage from './pages/AdminPage'

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

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App