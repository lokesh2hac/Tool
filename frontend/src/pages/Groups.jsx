import { useState, useEffect } from 'react'
import {
  getScannedGroups,
  scanGroups,
  generateRecruitmentPost,
  sendPostToGroups,
  getGroupMessages,
  checkGroupPermissions
} from '../api'

export default function Groups({ showToast }) {
  const [groups, setGroups] = useState([])
  const [selected, setSelected] = useState({})
  const [keyword, setKeyword] = useState('')
  const [scanning, setScanning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [generating, setGenerating] = useState(false)
  const [sending, setSending] = useState(false)
  const [brandName, setBrandName] = useState('ACE2KING')
  const [expandedGroup, setExpandedGroup] = useState(null)
  const [groupMessages, setGroupMessages] = useState({})
  const [permissions, setPermissions] = useState({})
  const [sendResults, setSendResults] = useState([])
  const [showResults, setShowResults] = useState(false)
  const [joinFirst, setJoinFirst] = useState(false)

  const fetchGroups = async () => {
    setLoading(true)
    try {
      const data = await getScannedGroups()
      setGroups(data || [])
      const sel = {}
      data.forEach(g => sel[g.group_username] = true)
      setSelected(sel)
    } catch (err) {
      showToast('Failed to load groups', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchGroups()
  }, [])

  const handleScan = async () => {
    if (!keyword.trim()) return showToast('Enter a keyword', 'error')
    setScanning(true)
    try {
      const result = await scanGroups(keyword)
      showToast(`Found ${result.total} groups`, 'success')
      await fetchGroups()
      setKeyword('')
    } catch (err) {
      showToast('Scan failed', 'error')
    } finally {
      setScanning(false)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const raw = await generateRecruitmentPost(brandName)
      let postText = raw
      // Try to parse if it looks like JSON
      try {
        if (raw.trim().startsWith('{') || raw.trim().startsWith('```json')) {
          // Remove markdown code fences if present
          let cleaned = raw.replace(/```json\s*/g, '').replace(/```\s*/g, '').trim()
          const parsed = JSON.parse(cleaned)
          postText = parsed.post || parsed.message || cleaned
        }
      } catch (e) {
        // Not JSON, use raw
        postText = raw
      }
      setMessage(postText)
      showToast('Message generated', 'success')
    } catch {
      showToast('Generation failed', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const copyMessage = () => {
    if (message) {
      navigator.clipboard.writeText(message)
      showToast('📋 Message copied!', 'success')
    }
  }

  const handleSend = async () => {
    const selectedUsernames = Object.keys(selected).filter(key => selected[key])
    if (selectedUsernames.length === 0) return showToast('Select at least one group', 'error')
    if (!message.trim()) return showToast('Enter or generate a message', 'error')
    setSending(true)
    setSendResults([])
    setShowResults(false)
    try {
      const result = await sendPostToGroups(selectedUsernames, message, 2.0, brandName, joinFirst)
      const success = result.results.filter(r => r.success).length
      setSendResults(result.results)
      setShowResults(true)
      showToast(`Sent to ${success}/${result.results.length} groups`, 'success')
    } catch (err) {
      showToast('Send failed', 'error')
    } finally {
      setSending(false)
    }
  }

  const toggleSelectAll = (val) => {
    const sel = {}
    groups.forEach(g => sel[g.group_username] = val)
    setSelected(sel)
  }

  const toggleGroupSelect = (username) => {
    setSelected({ ...selected, [username]: !selected[username] })
  }

  const handleViewMessages = async (username) => {
    if (expandedGroup === username) {
      setExpandedGroup(null)
      return
    }
    try {
      const data = await getGroupMessages(username)
      setGroupMessages({ ...groupMessages, [username]: data.messages || [] })
      setExpandedGroup(username)
    } catch (err) {
      showToast('Failed to fetch messages', 'error')
    }
  }

  const handleCheckPermissions = async (username) => {
    try {
      const canSend = await checkGroupPermissions(username)
      setPermissions({ ...permissions, [username]: canSend })
      showToast(`@${username}: ${canSend ? '✅ Can post' : '❌ Restricted'}`, canSend ? 'success' : 'error')
    } catch {
      showToast('Permission check failed', 'error')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-4 border-amber-500 border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-4 pb-24">
      <h1 className="text-2xl font-bold mb-2">👥 Group Management</h1>
      <p className="text-gray-400 text-sm mb-6">
        Scan groups by keyword, generate AI recruitment posts, and send them in bulk.
      </p>

      {/* Scan section */}
      <div className="bg-surface border border-gray-800 rounded-xl p-4 mb-6">
        <h2 className="font-semibold text-white mb-3">Scan New Groups</h2>
        <div className="flex flex-wrap gap-3">
          <input
            type="text"
            value={keyword}
            onChange={e => setKeyword(e.target.value)}
            placeholder="Enter keyword (e.g., betting, affiliate)"
            className="flex-1 min-w-[200px] bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-amber-500"
            disabled={scanning}
          />
          <button
            onClick={handleScan}
            disabled={scanning}
            className="btn-gold px-5 py-2 text-sm disabled:opacity-50"
          >
            {scanning ? 'Scanning...' : '🔍 Scan'}
          </button>
          <button
            onClick={fetchGroups}
            className="px-5 py-2 bg-gray-800 text-gray-300 rounded-lg hover:bg-gray-700 text-sm"
          >
            Refresh
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          Uses AI to expand keywords and saves up to 20 groups per keyword.
        </p>
      </div>

      {/* Groups list */}
      <div className="bg-surface border border-gray-800 rounded-xl p-4 mb-6">
        <div className="flex justify-between items-center mb-3">
          <h2 className="font-semibold text-white">
            Scanned Groups ({groups.length})
          </h2>
          <div className="flex gap-3 text-xs">
            <button
              onClick={() => toggleSelectAll(true)}
              className="text-amber-400 hover:text-amber-300"
            >
              Select All
            </button>
            <button
              onClick={() => toggleSelectAll(false)}
              className="text-gray-400 hover:text-gray-300"
            >
              Deselect All
            </button>
          </div>
        </div>

        {groups.length === 0 ? (
          <p className="text-gray-400 text-sm py-4 text-center">
            No groups scanned yet. Use the scan above to find groups.
          </p>
        ) : (
          <div className="max-h-80 overflow-y-auto space-y-2">
            {groups.map(g => (
              <div
                key={g.group_username}
                className="flex flex-wrap items-center gap-3 py-2 border-b border-gray-800 hover:bg-gray-800/30 px-2 rounded-lg"
              >
                <input
                  type="checkbox"
                  checked={selected[g.group_username] || false}
                  onChange={() => toggleGroupSelect(g.group_username)}
                  className="w-4 h-4 accent-amber-500 cursor-pointer"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm truncate">{g.group_title}</p>
                  <p className="text-gray-500 text-xs truncate">
                    @{g.group_username} • {g.member_count || 0} members
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleCheckPermissions(g.group_username)}
                    className="text-xs text-blue-400 hover:text-blue-300 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-1 rounded"
                  >
                    {permissions[g.group_username] === true
                      ? '✅'
                      : permissions[g.group_username] === false
                      ? '❌'
                      : '🔍'}
                  </button>
                  <button
                    onClick={() => handleViewMessages(g.group_username)}
                    className="text-xs text-gray-400 hover:text-white bg-gray-700/30 hover:bg-gray-700/50 px-2 py-1 rounded"
                  >
                    {expandedGroup === g.group_username ? 'Hide' : 'View'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {expandedGroup && groupMessages[expandedGroup] && (
          <div className="mt-3 p-3 bg-gray-900/50 rounded-lg max-h-60 overflow-y-auto">
            <p className="text-xs font-semibold text-gray-400 mb-2">
              📩 Messages from @{expandedGroup} (showing last {groupMessages[expandedGroup].length})
            </p>
            {groupMessages[expandedGroup].length === 0 ? (
              <p className="text-gray-500 text-sm">No messages found.</p>
            ) : (
              groupMessages[expandedGroup].slice(0, 10).map((msg, idx) => (
                <div key={idx} className="text-sm text-gray-300 border-b border-gray-800 py-1">
                  <span className="text-amber-400 font-medium">
                    {msg.sender_name || 'Unknown'}
                  </span>
                  : {msg.text}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Message section */}
      <div className="bg-surface border border-gray-800 rounded-xl p-4 mb-6">
        <div className="flex flex-wrap justify-between items-center gap-3 mb-3">
          <h2 className="font-semibold text-white">✍️ Recruitment Post</h2>
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={brandName}
              onChange={e => setBrandName(e.target.value)}
              placeholder="Brand"
              className="w-28 bg-gray-800 border border-gray-700 text-white text-sm rounded-lg px-2 py-1 focus:outline-none focus:border-amber-500"
            />
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="btn-gold px-3 py-1 text-sm disabled:opacity-50"
            >
              {generating ? '...' : '✨ Generate AI'}
            </button>
            {message && (
              <button
                onClick={copyMessage}
                className="px-3 py-1 bg-gray-700 text-white text-sm rounded-lg hover:bg-gray-600"
                title="Copy message"
              >
                📋 Copy
              </button>
            )}
          </div>
        </div>
        <textarea
          value={message}
          onChange={e => setMessage(e.target.value)}
          rows={4}
          placeholder="Enter your recruitment message or generate with AI (max 300 chars)"
          className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-amber-500"
          maxLength={300}
        />
        <p className="text-gray-500 text-xs mt-1">
          {message.length}/300 characters • No @username to avoid spam filters
        </p>
      </div>

      {/* Join & Post checkbox */}
      <div className="flex items-center gap-2 mt-3 mb-4">
        <input
          type="checkbox"
          checked={joinFirst}
          onChange={(e) => setJoinFirst(e.target.checked)}
          className="w-4 h-4 accent-amber-500"
          disabled={sending}
        />
        <label className="text-sm text-gray-300">
          Join group before posting (if not already a member)
        </label>
      </div>

      {/* Send button */}
      <button
        onClick={handleSend}
        disabled={sending || groups.length === 0}
        className="w-full btn-gold py-3 text-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {sending ? '📤 Sending...' : '📤 Send Post to Selected Groups'}
      </button>

      {/* Results section */}
      {showResults && sendResults.length > 0 && (
        <div className="mt-4 bg-surface border border-gray-800 rounded-xl p-4 max-h-60 overflow-y-auto">
          <h3 className="font-semibold text-white mb-2">📋 Send Results</h3>
          {sendResults.map((r, idx) => (
            <div key={idx} className="flex items-center gap-3 py-1 border-b border-gray-800 text-sm">
              <span className={r.success ? 'text-green-400' : 'text-red-400'}>
                {r.success ? '✅' : '❌'}
              </span>
              <span className="text-gray-300">@{r.group}</span>
              {!r.success && <span className="text-red-400 text-xs">{r.error}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
