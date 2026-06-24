import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api'
import GroupCard from '../components/GroupCard'
import ApiKeyModal from '../components/ApiKeyModal'

export default function Dashboard({ showToast }) {
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')
  const [groups, setGroups] = useState([])
  const [selectedGroups, setSelectedGroups] = useState([])
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [analyzeProgress, setAnalyzeProgress] = useState([])
  const [analyzing, setAnalyzing] = useState(false)
  const [aiKeywords, setAiKeywords] = useState([]) // show user what AI searched

  // Active Gemini key chosen by the user (from ApiKeyModal)
  const [activeGeminiKey, setActiveGeminiKey] = useState(null) // { id, label }
  // Rate-limit popup state
  const [rateLimitState, setRateLimitState] = useState(null) // { groupIndex, rateLimitedKeyId, resolveKey }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!keyword.trim()) return
    setLoadingSearch(true)
    setGroups([])
    setSelectedGroups([])
    setAiKeywords([])
    try {
      const res = await api.post('/api/groups/search', { keyword })
      const data = res.data || {}
      const foundGroups = data.groups || (Array.isArray(res.data) ? res.data : [])
      const keywords = data.keywords_used || []
      setGroups(foundGroups)
      setAiKeywords(keywords)
      if (foundGroups.length === 0) {
        showToast('No public groups found. Try a different keyword.', 'error')
      } else {
        showToast(`Found ${foundGroups.length} groups using AI-expanded keywords!`, 'success')
      }
    } catch (err) {
      const detail = err.response?.data?.detail || 'Search failed'
      showToast(detail, 'error')
      // If 401, session expired
      if (err.response?.status === 401) {
        showToast('Session expired. Please login again.', 'error')
      }
    } finally {
      setLoadingSearch(false)
    }
  }

  const toggleGroup = (group) => {
    setSelectedGroups(prev => {
      const key = group.group_username || group.group_title
      const exists = prev.find(g => (g.group_username || g.group_title) === key)
      if (exists) return prev.filter(g => (g.group_username || g.group_title) !== key)
      return [...prev, group]
    })
  }

  const isSelected = (group) => {
    const key = group.group_username || group.group_title
    return !!selectedGroups.find(g => (g.group_username || g.group_title) === key)
  }

  /**
   * Show the key-picker modal and wait for the user to pick a key.
   * Returns the selected key object or null if the user cancelled.
   */
  const waitForKeySelection = (rateLimitedKeyId) => {
    return new Promise((resolve) => {
      setRateLimitState({ rateLimitedKeyId, resolveKey: resolve })
    })
  }

  const handleKeySelected = async (key) => {
    // Fetch the full (unmasked) api_key from the backend for this key id
    // The backend returns masked keys in list, but we pass the key object
    // The user selected a key — we need to get the actual api_key value.
    // Since the backend masks keys, we store a reference. The backend
    // analyze endpoint accepts gemini_key_id + gemini_api_key; to get the
    // actual key, we rely on the backend to look it up by ID.
    // We pass key_id and leave gemini_api_key empty — the backend will use
    // the stored key from DB.  But the current design passes api_key in body.
    // To avoid exposing the key to the frontend we send only gemini_key_id and
    // let the backend resolve it. We update candidates.py to support that pattern.
    // For now, store the selected key id so analysis uses it.
    const selected = { id: key.id, label: key.label }
    setActiveGeminiKey(selected)
    if (rateLimitState?.resolveKey) {
      rateLimitState.resolveKey(selected)
    }
    setRateLimitState(null)
  }

  const handleModalClose = () => {
    if (rateLimitState?.resolveKey) {
      rateLimitState.resolveKey(null)
    }
    setRateLimitState(null)
  }

  const handleAnalyze = async () => {
    if (selectedGroups.length === 0) {
      showToast('Please select at least one group', 'error')
      return
    }
    setAnalyzing(true)
    setAnalyzeProgress(selectedGroups.map(g => ({ group: g, status: 'pending' })))

    // Use whatever active key the user has selected (may be null = use env default)
    let currentKeyId = activeGeminiKey?.id || null

    for (let i = 0; i < selectedGroups.length; i++) {
      const group = selectedGroups[i]
      const groupKey = group.group_username || group.group_title

      setAnalyzeProgress(prev =>
        prev.map((p, idx) => idx === i ? { ...p, status: 'fetching' } : p)
      )

      let retryWithNewKey = true
      while (retryWithNewKey) {
        retryWithNewKey = false
        try {
          const msgRes = await api.post('/api/groups/messages', { group_username: groupKey })
          const messages = msgRes.data.messages || []

          setAnalyzeProgress(prev =>
            prev.map((p, idx) => idx === i ? { ...p, status: 'analyzing' } : p)
          )

          await api.post('/api/candidates/analyze', {
            group_username: groupKey,
            group_id: group.id || null,
            messages,
            gemini_key_id: currentKeyId || undefined,
          })

          setAnalyzeProgress(prev =>
            prev.map((p, idx) => idx === i ? { ...p, status: 'done' } : p)
          )
        } catch (err) {
          if (err.response?.status === 429) {
            const rateLimitedKeyId = err.response?.data?.detail?.key_id || currentKeyId
            setAnalyzeProgress(prev =>
              prev.map((p, idx) => idx === i ? { ...p, status: 'rate_limited' } : p)
            )
            // Show modal and wait for user to select a new key
            const newKey = await waitForKeySelection(rateLimitedKeyId)
            if (newKey) {
              currentKeyId = newKey.id
              setActiveGeminiKey(newKey)
              retryWithNewKey = true // retry this group with the new key
            } else {
              // User cancelled
              setAnalyzeProgress(prev =>
                prev.map((p, idx) => idx === i ? { ...p, status: 'error', error: 'Cancelled (rate limit)' } : p)
              )
            }
          } else {
            setAnalyzeProgress(prev =>
              prev.map((p, idx) => idx === i ? { ...p, status: 'error', error: err.response?.data?.detail } : p)
            )
          }
        }
      }
    }

    setAnalyzing(false)
    showToast('Analysis complete! Redirecting to candidates...', 'success')
    setTimeout(() => navigate('/candidates'), 1500)
  }

  const statusIcon = (status) => {
    if (status === 'pending') return '⏳'
    if (status === 'fetching') return '📥'
    if (status === 'analyzing') return '🤖'
    if (status === 'done') return '✅'
    if (status === 'error') return '❌'
    if (status === 'rate_limited') return '⚠️'
    return ''
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Rate limit modal */}
      {rateLimitState && (
        <ApiKeyModal
          rateLimitedKeyId={rateLimitState.rateLimitedKeyId}
          onKeySelected={handleKeySelected}
          onClose={handleModalClose}
        />
      )}

      {/* Search Section */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-white mb-1">Find Affiliate Candidates</h1>
        <p className="text-gray-400 mb-6">
          Enter an iGaming brand or keyword — <span className="text-amber-400">Gemini AI</span> will expand it into smart search terms and find relevant Telegram groups
        </p>

        <form onSubmit={handleSearch} className="flex gap-3">
          <input
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="e.g. 1xbet, dream11, betway affiliate, igaming promoter..."
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-500 transition-colors"
          />
          <button type="submit" disabled={loadingSearch} className="btn-gold px-8">
            {loadingSearch ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-gray-900 border-t-transparent rounded-full animate-spin" />
                AI Searching...
              </span>
            ) : '🔍 Find Groups'}
          </button>
        </form>

        {/* Show AI-generated keywords */}
        {aiKeywords.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 items-center">
            <span className="text-xs text-gray-500">🤖 Gemini searched for:</span>
            {aiKeywords.map((kw, i) => (
              <span key={i} className="text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-1 rounded-full">
                {kw}
              </span>
            ))}
          </div>
        )}

        {/* Active Gemini key indicator */}
        {activeGeminiKey && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-xs text-green-400">🔑 Using key:</span>
            <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-1 rounded-full">
              {activeGeminiKey.label}
            </span>
          </div>
        )}
      </div>

      {/* Groups Results */}
      {groups.length > 0 && (
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">
              Found {groups.length} Groups
              {selectedGroups.length > 0 && (
                <span className="ml-2 text-amber-400 text-sm">({selectedGroups.length} selected)</span>
              )}
            </h2>
            {groups.length > 0 && (
              <button
                onClick={() => setSelectedGroups(selectedGroups.length === groups.length ? [] : [...groups])}
                className="text-sm text-amber-400 hover:text-amber-300 transition-colors"
              >
                {selectedGroups.length === groups.length ? 'Deselect All' : 'Select All'}
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {groups.map((group, idx) => (
              <GroupCard
                key={group.id || idx}
                group={group}
                selected={isSelected(group)}
                onToggle={() => toggleGroup(group)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Analyze Button */}
      {selectedGroups.length > 0 && !analyzing && analyzeProgress.length === 0 && (
        <div className="sticky bottom-6 flex justify-center">
          <button onClick={handleAnalyze} className="btn-gold px-12 py-4 text-lg shadow-2xl shadow-amber-500/30">
            🤖 Analyze {selectedGroups.length} Selected Group{selectedGroups.length > 1 ? 's' : ''} with AI
          </button>
        </div>
      )}

      {/* Progress */}
      {analyzeProgress.length > 0 && (
        <div className="bg-surface rounded-xl border border-gray-800 p-6">
          <h3 className="text-white font-semibold mb-4">
            {analyzing ? '⚡ AI Analyzing groups...' : '✅ Analysis Complete'}
          </h3>
          <div className="space-y-3">
            {analyzeProgress.map((p, idx) => (
              <div key={idx} className="flex items-center gap-3 text-sm">
                <span className="text-lg">{statusIcon(p.status)}</span>
                <span className="text-white font-medium">{p.group.group_title}</span>
                <span className="text-gray-400">
                  {p.status === 'fetching' && 'Fetching last 100 messages...'}
                  {p.status === 'analyzing' && 'Gemini AI scoring candidates...'}
                  {p.status === 'done' && 'Done ✓'}
                  {p.status === 'pending' && 'Waiting...'}
                  {p.status === 'rate_limited' && '⚠️ Rate limited — pick a new key...'}
                  {p.status === 'error' && `Error: ${p.error || 'Unknown error'}`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
