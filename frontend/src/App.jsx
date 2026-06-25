import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import api from './api'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Candidates from './pages/Candidates'
import Outreach from './pages/Outreach'
import OutreachHistory from './pages/OutreachHistory'
import ApiKeys from './pages/ApiKeys'
import AutoScanPage from './pages/AutoScanPage'  // 👈 new import
import TopBar from './components/TopBar'
import BottomNav from './components/BottomNav'
import Toast from './components/Toast'

export default function App() {
  const [auth, setAuth] = useState(null)
  const [toast, setToast] = useState(null)

  const TOAST_DURATION_MS = 3000

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), TOAST_DURATION_MS)
  }

  useEffect(() => {
    // Use centralized api instance so VITE_API_URL is respected
    api.get('/api/auth/status')
      .then(res => setAuth(res.data))
      .catch(() => setAuth({ logged_in: false }))
  }, [])

  if (auth === null) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <BrowserRouter>
      {auth.logged_in && <TopBar auth={auth} setAuth={setAuth} showToast={showToast} />}
      {toast && <Toast message={toast.message} type={toast.type} />}
      <div className={auth.logged_in ? 'pb-20' : ''}>
        <Routes>
          <Route
            path="/"
            element={auth.logged_in ? <Navigate to="/dashboard" replace /> : <Login setAuth={setAuth} showToast={showToast} />}
          />
          <Route
            path="/dashboard"
            element={auth.logged_in ? <Dashboard showToast={showToast} /> : <Navigate to="/" replace />}
          />
          <Route
            path="/candidates"
            element={auth.logged_in ? <Candidates showToast={showToast} /> : <Navigate to="/" replace />}
          />
          <Route
            path="/outreach"
            element={auth.logged_in ? <Outreach /> : <Navigate to="/" replace />}
          />
          <Route
            path="/outreach-history"
            element={auth.logged_in ? <OutreachHistory /> : <Navigate to="/" replace />}
          />
          <Route
            path="/api-keys"
            element={auth.logged_in ? <ApiKeys showToast={showToast} /> : <Navigate to="/" replace />}
          />
          {/* 👇 New route for auto-scan */}
          <Route
            path="/auto-scan"
            element={auth.logged_in ? <AutoScanPage showToast={showToast} /> : <Navigate to="/" replace />}
          />
          {/* Catch-all — redirect unknown paths to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      {auth.logged_in && <BottomNav />}
    </BrowserRouter>
  )
}
