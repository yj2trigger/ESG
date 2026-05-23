import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import GenderSelectPage from './pages/GenderSelectPage'

function App() {
  const gender = useAuthStore((s) => s.gender)

  return (
    <Routes>
      <Route path="/gender" element={<GenderSelectPage />} />
      <Route
        path="/"
        element={
          gender
            ? <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>메인 화면 (준비 중...)</div>
            : <Navigate to="/gender" replace />
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
