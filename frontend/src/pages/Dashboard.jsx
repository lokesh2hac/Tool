import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import GroupCard from '../components/GroupCard'

export default function Dashboard({ showToast }) {
  const navigate = useNavigate()
  const [keyword, setKeyword] = useState('')
  const [groups, setGroups] = useState([])
  const [selectedGroups, setSelectedGroups] = useState([])
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [analyzeProgress, setAnalyzeProgress] = useState([])
  const [analyzing, setAnalyzing] = useState(false)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!keyword.trim()) return
    setLoadingSearch(true)
    setGroups([])
    setSelectedGroups([])
    try {
      const res = await axios.post('/api/groups/search', { keyword }, { withCredentials: true })
      setGroups(res.data || [])
      if ((res.data || []).length === 0) {
        showToast('No groups found for this keyword', 'error')
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Search failed', 'error')
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

  const handleAnalyze = async () => {
    if (selectedGroups.length === 0) {
      showToast('Please select at least one group', 'error')
      return
    }
    setAnalyzing(true)
    setAnalyzeProgress(selectedGroups.map(g => ({ group: g, status: 'pending' })))

    for (let i = 0; i < selectedGroups.length; i++) {
      const group = selectedGroups[i]
      const groupKey = group.group_username || group.group_title

      // Update to 'fetching'
      setAnalyzeProgress(prev =>
        prev.map((p, idx) => idx === i ? { ...p, status: 'fetching' } : p)
      )

      try {
        const msgRes = await axios.post('/api/groups/messages', { group_username: groupKey }, { withCredentials: true })
        const messages = msgRes.data.messages || []

        setAnalyzeProgress(prev =>
          prev.map((p, idx) => idx === i ? { ...p, status: 'analyzing' } : p)
        )

        await axios.post('/api/candidates/analyze', {
          group_username: groupKey,
          group_id: group.id || null,
          messages,
        }, { withCredentials: true })

        setAnalyzeProgress(prev =>
          prev.map((p, idx) => idx === i ? { ...p, status: 'done' } : p)
        )
      } catch (err) {
        setAnalyzeProgress(prev =>
          prev.map((p, idx) => idx === i ? { ...p, status: 'error', error: err.response?.data?.detail } : p)
        )
      }
    }

    setAnalyzing(false)
    showToast('Analysis complete! Redirecting to candidates...', 'success')
    const REDIRECT_DELAY_MS = 1500
    setTimeout(() => navigate('/candidates'), REDIRECT_DELAY_MS)
  }

  const statusIcon = (status) => {
    if (status === 'pending') return '⏳'
    if (status === 'fetching') return '📥'
    if (status === 'analyzing') return '🤖'
    if (status === 'done') return '✅'
    if (status === 'error') return '❌'
    return ''
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Search Section */}
      <div className="mb-10">
        <h1 className="text-2xl font-bold text-white mb-1">Find Affiliate Candidates</h1>
        <p className="text-gray-400 mb-6">Enter an iGaming brand or keyword to discover relevant Telegram groups</p>

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
                Searching...
              </span>
            ) : '🔍 Find Groups'}
          </button>
        </form>
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

      {/* Analyze Section */}
      {selectedGroups.length > 0 && !analyzing && analyzeProgress.length === 0 && (
        <div className="sticky bottom-6 flex justify-center">
          <button onClick={handleAnalyze} className="btn-gold px-12 py-4 text-lg shadow-2xl shadow-amber-500/30">
            🤖 Analyze {selectedGroups.length} Selected Group{selectedGroups.length > 1 ? 's' : ''}
          </button>
        </div>
      )}

      {/* Progress */}
      {analyzeProgress.length > 0 && (
        <div className="bg-surface rounded-xl border border-gray-800 p-6">
          <h3 className="text-white font-semibold mb-4">
            {analyzing ? '⚡ Analyzing groups...' : '✅ Analysis Complete'}
          </h3>
          <div className="space-y-3">
            {analyzeProgress.map((p, idx) => (
              <div key={idx} className="flex items-center gap-3 text-sm">
                <span className="text-lg">{statusIcon(p.status)}</span>
                <span className="text-white font-medium">{p.group.group_title}</span>
                <span className="text-gray-400">
                  {p.status === 'fetching' && 'Fetching messages...'}
                  {p.status === 'analyzing' && 'Analyzing with AI...'}
                  {p.status === 'done' && 'Done'}
                  {p.status === 'pending' && 'Waiting...'}
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
