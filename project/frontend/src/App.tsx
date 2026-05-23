import { Routes, Route, Navigate } from 'react-router-dom'

// 페이지는 기능 구현 시 순서대로 추가됩니다
// 현재: 기능 2 (성별 선택) 구현 예정

function App() {
  return (
    <Routes>
      <Route path="/" element={<div>준비 중...</div>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
