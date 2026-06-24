import { useState, useEffect } from 'react'
import axios from 'axios'
import OutreachModal from '../components/OutreachModal'

export default function Candidates({ showToast }) {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [filterScore, setFilterScore] = useState(0)
  const [expandedMsg, setExpandedMsg] = useState({})

  useEffect(() => {
    axios.get('/api/candidates', { withCredentials: true })
      .then(res => setCandidates(res.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = candidates.filter(c => (c.ai_score || 0) >= filterScore)

  const scoreBadge = (score) => {
    if (score >= 8) return 'bg-green-500/20 text-green-400 border-green-500/30'
    if (score >= 6) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
    return 'bg-red-500/20 text-red-400 border-red-500/30'
  }

  const toggleMsg = (id) => setExpandedMsg(prev => ({ ...prev, [id]: !prev[id] }))

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Candidates</h1>
          <p className="text-gray-400">{filtered.length} potential affiliate candidates found</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-400">Min Score:</label>
          <select
            value={filterScore}
            onChange={e => setFilterScore(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
          >
            <option value={0}>All</option>
            <option value={6}>6+</option>
            <option value={7}>7+</option>
            <option value={8}>8+</option>
            <option value={9}>9+</option>
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-surface rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-4xl mb-4">🎯</p>
          <p className="text-gray-400 text-lg">No candidates yet.</p>
          <p className="text-gray-500 text-sm mt-1">Go to Dashboard, search for groups and analyze them to find candidates.</p>
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-gray-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">#</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Name</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Username</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Score</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">AI Reason</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Sample Message</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Status</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((c, idx) => (
                  <tr key={c.id || idx} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-4 text-gray-400">{idx + 1}</td>
                    <td className="px-4 py-4 text-white font-medium">{c.display_name || '—'}</td>
                    <td className="px-4 py-4 text-amber-400">{c.telegram_username || '—'}</td>
                    <td className="px-4 py-4">
                      <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold border ${scoreBadge(c.ai_score)}`}>
                        {c.ai_score}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-gray-300 max-w-xs">
                      <span className="text-xs">{c.ai_reason || '—'}</span>
                    </td>
                    <td className="px-4 py-4 text-gray-400 max-w-xs">
                      {c.message_sample ? (
                        <div className="text-xs">
                          {expandedMsg[c.id] ? c.message_sample : c.message_sample.slice(0, 80)}
                          {c.message_sample.length > 80 && (
                            <button
                              onClick={() => toggleMsg(c.id)}
                              className="text-amber-400 ml-1 hover:underline"
                            >
                              {expandedMsg[c.id] ? ' less' : '...more'}
                            </button>
                          )}
                        </div>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        c.status === 'contacted'
                          ? 'bg-blue-500/20 text-blue-400'
                          : 'bg-gray-700 text-gray-300'
                      }`}>
                        {c.status || 'new'}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <button
                        onClick={() => setSelectedCandidate(c)}
                        disabled={c.status === 'contacted'}
                        className="bg-amber-500 hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed text-gray-900 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
                      >
                        {c.status === 'contacted' ? '✓ Sent' : '📨 Outreach'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedCandidate && (
        <OutreachModal
          candidate={selectedCandidate}
          showToast={showToast}
          onClose={() => setSelectedCandidate(null)}
          onSent={(id) => {
            setCandidates(prev => prev.map(c => c.id === id ? { ...c, status: 'contacted' } : c))
            setSelectedCandidate(null)
          }}
        />
      )}
    </div>
  )
}
