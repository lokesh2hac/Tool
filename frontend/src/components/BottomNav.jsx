import { Link, useLocation } from 'react-router-dom'

const tabs = [
  { to: '/dashboard', icon: '🔍', label: 'Search' },
  { to: '/candidates', icon: '🎯', label: 'Candidates' },
  { to: '/outreach', icon: '📨', label: 'Outreach' },
  { to: '/outreach-history', icon: '📬', label: 'History' },
  { to: '/auto-scan', icon: '🤖', label: 'Auto Scan' }, // 👈 new
]

export default function BottomNav() {
  const location = useLocation()

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 border-t border-gray-800 bg-[#0f1420]">
      <div className="max-w-6xl mx-auto grid grid-cols-5"> {/* 👈 changed from grid-cols-4 to grid-cols-5 */}
        {tabs.map(tab => {
          const active = location.pathname === tab.to
          return (
            <Link
              key={tab.to}
              to={tab.to}
              className={`flex flex-col items-center justify-center gap-1 py-2.5 transition-colors duration-150 ${
                active ? 'text-amber-400' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <span className={`text-[10px] leading-none ${active ? 'text-amber-400' : 'text-transparent'}`}>
                ●
              </span>
              <span className="text-xl leading-none">{tab.icon}</span>
              <span className="text-[11px] font-medium">{tab.label}</span>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
