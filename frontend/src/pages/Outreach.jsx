import { useState, useEffect } from 'react'
import axios from 'axios'

export default function Outreach() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedMsg, setExpandedMsg] = useState({})

  useEffect(() => {
    axios.get('/api/outreach/history', { withCredentials: true })
      .then(res => setLogs(res.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const toggleMsg = (id) => setExpandedMsg(prev => ({ ...prev, [id]: !prev[id] }))

  const formatDate = (dateStr) => {
    if (!dateStr) return '—'
    return new Date(dateStr).toLocaleString()
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Outreach History</h1>
        <p className="text-gray-400">{logs.length} messages sent</p>
      </div>

      {logs.length === 0 ? (
        <div className="bg-surface rounded-xl border border-gray-800 p-12 text-center">
          <p className="text-4xl mb-4">📬</p>
          <p className="text-gray-400 text-lg">No outreach messages sent yet.</p>
          <p className="text-gray-500 text-sm mt-1">Find candidates and send outreach messages from the Candidates page.</p>
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-gray-800 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-900/50">
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Date</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Candidate</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Group Source</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Message</th>
                  <th className="text-left px-4 py-3 text-gray-400 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log, idx) => (
                  <tr key={log.id || idx} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-4 text-gray-400 whitespace-nowrap text-xs">
                      {formatDate(log.sent_at)}
                    </td>
                    <td className="px-4 py-4 text-amber-400 font-medium">
                      {log.candidate_username}
                    </td>
                    <td className="px-4 py-4 text-gray-300 text-xs">
                      {log.group_source || '—'}
                    </td>
                    <td className="px-4 py-4 text-gray-400 max-w-sm">
                      <div className="text-xs">
                        {expandedMsg[log.id]
                          ? log.message_sent
                          : (log.message_sent || '').slice(0, 100)}
                        {(log.message_sent || '').length > 100 && (
                          <button
                            onClick={() => toggleMsg(log.id)}
                            className="text-amber-400 ml-1 hover:underline"
                          >
                            {expandedMsg[log.id] ? ' less' : '...more'}
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <span className="bg-green-500/20 text-green-400 border border-green-500/30 text-xs px-2 py-1 rounded-full">
                        Sent
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
