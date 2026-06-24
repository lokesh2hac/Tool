import { Link, useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'

export default function Navbar({ auth, setAuth, showToast }) {
  const location = useLocation()
  const navigate = useNavigate()

  const handleLogout = async () => {
    try {
      await axios.post('/api/auth/logout', {}, { withCredentials: true })
      setAuth({ logged_in: false })
      navigate('/')
      showToast('Logged out successfully', 'success')
    } catch {
      showToast('Logout failed', 'error')
    }
  }

  const navLink = (to, label) => {
    const active = location.pathname === to
    return (
      <Link
        to={to}
        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
          active
            ? 'bg-amber-500/20 text-amber-400'
            : 'text-gray-300 hover:text-white hover:bg-gray-800'
        }`}
      >
        {label}
      </Link>
    )
  }

  return (
    <nav className="bg-surface border-b border-gray-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        {/* Logo */}
        <Link to="/dashboard" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center">
            <span className="text-gray-900 font-black text-sm">A2K</span>
          </div>
          <span className="text-white font-bold text-lg">ACE2KING</span>
        </Link>

        {/* Nav Links */}
        <div className="hidden md:flex items-center gap-1">
          {navLink('/dashboard', '🔍 Dashboard')}
          {navLink('/candidates', '🎯 Candidates')}
          {navLink('/outreach', '📬 Outreach History')}
        </div>

        {/* User + Logout */}
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            {auth.username && (
              <p className="text-amber-400 text-sm font-medium">@{auth.username}</p>
            )}
            <p className="text-gray-500 text-xs">{auth.phone}</p>
          </div>
          <button
            onClick={handleLogout}
            className="bg-gray-800 hover:bg-red-500/20 hover:text-red-400 text-gray-300 text-sm px-3 py-2 rounded-lg transition-colors border border-gray-700"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  )
}
