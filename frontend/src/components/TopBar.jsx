import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../api'
import { DEFAULT_MODEL, MODEL_OPTIONS, getStoredModel, setStoredModel } from '../modelConfig'

export default function TopBar({ auth, setAuth, showToast }) {
  const navigate = useNavigate()
  const menuRef = useRef(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [showModels, setShowModels] = useState(false)
  const [selectedModel, setSelectedModel] = useState(() => getStoredModel())

  // Session switcher state
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState('')
  const [loadingSessions, setLoadingSessions] = useState(false)

  useEffect(() => {
    setStoredModel(selectedModel || DEFAULT_MODEL)
  }, [selectedModel])

  // Fetch sessions and active one on mount
  useEffect(() => {
    const fetchSessions = async () => {
      try {
        setLoadingSessions(true)
        const [listRes, activeRes] = await Promise.all([
          api.get('/api/sessions'),
          api.get('/api/sessions/active'),
        ])
        setSessions(listRes.data || [])
        setActiveSession(activeRes.data?.active || '')
      } catch (err) {
        // Silently fail – sessions are optional
      } finally {
        setLoadingSessions(false)
      }
    }
    fetchSessions()
  }, [])

  const handleSwitchSession = async (phone) => {
    try {
      await api.post('/api/sessions/active', { phone })
      setActiveSession(phone)
      showToast(`Switched to ${phone}`, 'success')
      setMenuOpen(false)
    } catch (err) {
      showToast('Failed to switch session', 'error')
    }
  }

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false)
        setShowModels(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    try {
      await api.post('/api/auth/logout', {})
      setAuth({ logged_in: false })
      setMenuOpen(false)
      setShowModels(false)
      navigate('/')
      showToast('Logged out successfully', 'success')
    } catch {
      showToast('Logout failed', 'error')
    }
  }

  const handleModelChange = (model) => {
    setSelectedModel(model)
  }

  return (
    <div className="sticky top-0 z-50 border-b border-gray-800 bg-[#0a0e1a]">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link to="/dashboard" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center">
            <span className="text-gray-900 font-black text-sm">A2K</span>
          </div>
          <span className="text-white font-bold text-lg">ACE2KING</span>
        </Link>

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => {
              setMenuOpen(open => !open)
              setShowModels(false)
            }}
            className="w-10 h-10 rounded-xl border border-gray-700 bg-[#1a2035] text-gray-300 hover:text-white transition-colors duration-150"
            aria-label="Open settings"
          >
            ⋮
          </button>

          {menuOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-xl border border-gray-700 bg-[#1a2035] shadow-xl overflow-hidden">
              {/* API Keys */}
              <button
                type="button"
                onClick={() => {
                  navigate('/api-keys')
                  setMenuOpen(false)
                  setShowModels(false)
                }}
                className="w-full px-4 py-3 text-left text-sm text-gray-200 hover:bg-white/5 transition-colors duration-150"
              >
                🔑 API Keys
              </button>

              {/* Model switcher */}
              <button
                type="button"
                onClick={() => setShowModels(value => !value)}
                className="w-full px-4 py-3 text-left text-sm text-gray-200 hover:bg-white/5 transition-colors duration-150 flex items-center justify-between"
              >
                <span>🤖 Change Model</span>
                <span className="text-gray-500">{showModels ? '−' : '+'}</span>
              </button>

              {showModels && (
                <div className="px-4 pb-4">
                  <div className="rounded-xl border border-gray-700 bg-[#0f1420] p-3">
                    <p className="text-xs font-medium text-gray-400 mb-3">AI Model:</p>
                    <div className="space-y-2">
                      {MODEL_OPTIONS.map(option => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => handleModelChange(option.value)}
                          className="w-full text-left text-sm text-gray-200 hover:text-white transition-colors duration-150"
                        >
                          <span className={selectedModel === option.value ? 'text-amber-400' : 'text-gray-400'}>
                            {selectedModel === option.value ? '●' : '○'}
                          </span>{' '}
                          {option.label}
                          {option.note && <span className="text-gray-500"> ({option.note})</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Session Switcher */}
              <div className="border-t border-gray-700">
                <div className="px-4 py-3">
                  <p className="text-xs font-medium text-gray-400 mb-2">📱 Active Telegram Session</p>
                  {loadingSessions ? (
                    <div className="flex items-center gap-2 text-gray-500 text-sm">
                      <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                      Loading...
                    </div>
                  ) : sessions.length === 0 ? (
                    <p className="text-sm text-gray-500">No sessions saved yet.</p>
                  ) : (
                    <div className="space-y-1">
                      {sessions.map(s => (
                        <button
                          key={s.phone}
                          type="button"
                          onClick={() => handleSwitchSession(s.phone)}
                          className={`w-full text-left text-sm px-3 py-2 rounded-lg transition-colors flex items-center justify-between ${
                            s.phone === activeSession
                              ? 'bg-amber-500/10 text-amber-400'
                              : 'text-gray-300 hover:bg-white/5'
                          }`}
                        >
                          <span>{s.phone}</span>
                          {s.phone === activeSession && (
                            <span className="text-amber-400 text-xs">● Active</span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* User info */}
              <div className="border-t border-gray-700 px-4 py-3 text-sm text-gray-500">
                <p>{auth.username ? `@${auth.username}` : '@username'}</p>
                <p>{auth.phone || 'No phone'}</p>
              </div>

              {/* Logout */}
              <button
                type="button"
                onClick={handleLogout}
                className="w-full px-4 py-3 text-left text-sm text-red-400 hover:bg-red-500/10 transition-colors duration-150"
              >
                🚪 Logout
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
