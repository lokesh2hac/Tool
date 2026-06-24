import { useState } from 'react'
import axios from 'axios'

const DEFAULT_MESSAGE = (name) => `Hi ${name}! 👋

I'm from ACE2KING, a leading iGaming and sports betting platform.

We're looking for affiliate marketing partners and website promoters to join our commission-based program. Given your background, I think you'd be a great fit!

Would you be interested in learning more about our partnership opportunities? 💰

Best regards,
ACE2KING HR Team`

export default function OutreachModal({ candidate, showToast, onClose, onSent }) {
  const [message, setMessage] = useState(
    DEFAULT_MESSAGE(candidate.display_name || candidate.telegram_username || 'there')
  )
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!message.trim()) return
    setSending(true)
    try {
      await axios.post('/api/outreach/send', {
        candidate_username: candidate.telegram_username,
        message,
        candidate_id: candidate.id || candidate.db_id || null,
        group_source: candidate.group_username || null,
      }, { withCredentials: true })
      showToast('Message sent successfully! 🎉', 'success')
      onSent(candidate.id)
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to send message', 'error')
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="bg-surface rounded-2xl border border-gray-700 w-full max-w-lg shadow-2xl">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-white font-bold text-lg">Send Outreach</h3>
              <p className="text-amber-400 text-sm mt-0.5">
                {candidate.display_name && `${candidate.display_name} · `}
                {candidate.telegram_username}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-white text-2xl leading-none transition-colors"
            >
              ×
            </button>
          </div>
        </div>

        <div className="p-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">Message</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={10}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white text-sm focus:outline-none focus:border-amber-500 transition-colors resize-none"
          />
          <p className="text-gray-600 text-xs mt-1">{message.length} characters</p>
        </div>

        <div className="p-6 pt-0 flex gap-3">
          <button
            onClick={handleSend}
            disabled={sending}
            className="btn-gold flex-1 py-3 flex items-center justify-center gap-2"
          >
            {sending ? (
              <>
                <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
                Sending...
              </>
            ) : '📨 Send Message'}
          </button>
          <button
            onClick={onClose}
            className="px-6 py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
