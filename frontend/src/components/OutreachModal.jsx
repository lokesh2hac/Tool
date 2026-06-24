import { useState } from 'react'
import api from '../api'

const TEMPLATE = `Hi {name}! 👋

I'm from ACE2KING, a leading iGaming and sports betting platform.

We're looking for affiliate marketing partners and website promoters to join our commission-based program. Given your background, I think you'd be a great fit!

Would you be interested in learning more about our partnership opportunities? 💰

Best regards,
ACE2KING HR Team`

export default function OutreachModal({ candidate, onClose, showToast, onSent }) {
  const name = candidate.display_name || candidate.telegram_username || 'there'
  const [message, setMessage] = useState(TEMPLATE.replace('{name}', name))
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setSending(true)
    try {
      await api.post('/api/outreach/send', {
        candidate_username: candidate.telegram_username,
        candidate_id: candidate.id,
        group_source: candidate.group_username || '',
        message,
      })
      showToast(`Message sent to @${candidate.telegram_username}!`, 'success')
      onSent(candidate.telegram_username)
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to send message', 'error')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-gray-800 rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="p-6 border-b border-gray-800">
          <h3 className="text-white font-bold text-lg">Send Outreach</h3>
          <p className="text-gray-400 text-sm mt-1">
            To: <span className="text-amber-400">@{candidate.telegram_username}</span>
            {candidate.display_name && ` · ${candidate.display_name}`}
          </p>
        </div>
        <div className="p-6">
          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={10}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-amber-500 transition-colors resize-none"
          />
          <p className="text-xs text-gray-500 mt-2">{message.length} characters</p>
        </div>
        <div className="p-6 pt-0 flex gap-3">
          <button
            onClick={handleSend}
            disabled={sending}
            className="btn-gold flex-1 py-3"
          >
            {sending ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
                Sending...
              </span>
            ) : '📨 Send Message'}
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
