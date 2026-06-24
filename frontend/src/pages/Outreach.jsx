import { useState, useEffect } from 'react'
import api from '../api'

export default function Outreach() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    api.get('/api/outreach/history')
      .then(res => setLogs(res.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-white mb-2">📬 Outreach History</h1>
      <p className="text-gray-400 text-sm mb-6">{logs.length} messages sent</p>

      {logs.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-5xl mb-4">📭</p>
          <p className="text-gray-400">No outreach messages sent yet.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {logs.map((log, idx) => (
            <div key={log.id || idx} className="bg-surface border border-gray-800 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white font-medium">@{log.candidate_username}</p>
                  <p className="text-gray-500 text-xs mt-1">
                    {log.group_source && `From: ${log.group_source} · `}
                    {new Date(log.sent_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={() => setExpanded(expanded === idx ? null : idx)}
                  className="text-xs text-amber-400 hover:text-amber-300"
                >
                  {expanded === idx ? 'Hide' : 'View'}
                </button>
              </div>
              {expanded === idx && (
                <div className="mt-3 p-3 bg-gray-800/50 rounded-lg text-sm text-gray-300 whitespace-pre-wrap border-l-2 border-amber-500/40">
                  {log.message_sent}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
