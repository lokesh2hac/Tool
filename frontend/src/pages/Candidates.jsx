import { useState, useEffect } from 'react'
import api from '../api'
import OutreachModal from '../components/OutreachModal'

export default function Candidates({ showToast }) {
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedCandidate, setSelectedCandidate] = useState(null)
  const [minScore, setMinScore] = useState(6)

  useEffect(() => {
    api.get('/api/candidates')
      .then(res => setCandidates(res.data || []))
      .catch(() => showToast('Failed to load candidates', 'error'))
      .finally(() => setLoading(false))
  }, [])

  const filtered = candidates.filter(c => c.ai_score >= minScore)

  const scoreBadge = (score) => {
    if (score >= 8) return 'bg-green-500/20 text-green-400 border border-green-500/30'
    if (score >= 6) return 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
    return 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
  }

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-gray-400">Loading candidates...</p>
      </div>
    </div>
  )

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🎯 Candidates</h1>
          <p className="text-gray-400 text-sm mt-1">{filtered.length} potential affiliate agents found by Gemini AI</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-400">Min Score:</label>
          <select
            value={minScore}
            onChange={e => setMinScore(Number(e.target.value))}
            className="bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm"
          >
            {[6,7,8,9,10].map(s => <option key={s} value={s}>{s}+</option>)}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-5xl mb-4">🔍</p>
          <p className="text-gray-400 text-lg">No candidates found yet.</p>
          <p className="text-gray-500 text-sm mt-2">Go to Dashboard, search for groups and analyze them first.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered
            .sort((a, b) => b.ai_score - a.ai_score)
            .map((c, idx) => (
              <div key={c.id || idx} className="bg-surface border border-gray-800 rounded-xl p-5 hover:border-amber-500/30 transition-colors">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-white font-semibold">{c.display_name || 'Unknown'}</p>
                    <p className="text-amber-400 text-sm">@{c.telegram_username || 'no_username'}</p>
                  </div>
                  <span className={`text-lg font-bold px-3 py-1 rounded-lg ${scoreBadge(c.ai_score)}`}>
                    {c.ai_score}/10
                  </span>
                </div>
                <p className="text-gray-400 text-sm mb-2"><span className="text-gray-500">Reason:</span> {c.ai_reason}</p>
                {c.message_sample && (
                  <p className="text-gray-500 text-xs italic border-l-2 border-gray-700 pl-3 mb-4">
                    "{c.message_sample}"
                  </p>
                )}
                <button
                  onClick={() => setSelectedCandidate(c)}
                  disabled={c.status === 'contacted'}
                  className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                    c.status === 'contacted'
                      ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                      : 'btn-gold'
                  }`}
                >
                  {c.status === 'contacted' ? '✅ Already Contacted' : '📨 Send Outreach'}
                </button>
              </div>
            ))}
        </div>
      )}

      {selectedCandidate && (
        <OutreachModal
          candidate={selectedCandidate}
          onClose={() => setSelectedCandidate(null)}
          showToast={showToast}
          onSent={(username) => {
            setCandidates(prev =>
              prev.map(c => c.telegram_username === username ? { ...c, status: 'contacted' } : c)
            )
            setSelectedCandidate(null)
          }}
        />
      )}
    </div>
  )
}
