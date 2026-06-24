import { useState, useEffect } from 'react'
import api from '../api'

export default function ApiKeys({ showToast }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ label: '', provider: 'gemini', api_key: '' })
  const [showForm, setShowForm] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [clearingId, setClearingId] = useState(null)

  const fetchKeys = () => {
    setLoading(true)
    api.get('/api/api-keys')
      .then(res => setKeys(res.data || []))
      .catch(() => showToast('Failed to load API keys', 'error'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchKeys() }, [])

  const isRateLimited = (key) => {
    if (!key.rate_limited_until) return false
    return new Date(key.rate_limited_until) > new Date()
  }

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.label.trim() || !form.api_key.trim()) {
      showToast('Label and API key are required', 'error')
      return
    }
    setAdding(true)
    try {
      await api.post('/api/api-keys', form)
      showToast('API key added!', 'success')
      setForm({ label: '', provider: 'gemini', api_key: '' })
      setShowForm(false)
      fetchKeys()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to add key', 'error')
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (id) => {
    setDeletingId(id)
    try {
      await api.delete(`/api/api-keys/${id}`)
      showToast('API key deleted', 'success')
      setKeys(prev => prev.filter(k => k.id !== id))
    } catch {
      showToast('Failed to delete key', 'error')
    } finally {
      setDeletingId(null)
    }
  }

  const handleClearLimit = async (id) => {
    setClearingId(id)
    try {
      await api.post(`/api/api-keys/${id}/clear-rate-limit`)
      showToast('Rate limit cleared', 'success')
      fetchKeys()
    } catch {
      showToast('Failed to clear rate limit', 'error')
    } finally {
      setClearingId(null)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🔑 API Keys</h1>
          <p className="text-gray-400 text-sm mt-1">
            Manage Gemini API keys for AI analysis. When one key hits the rate limit, switch to another.
          </p>
        </div>
        <button
          onClick={() => setShowForm(v => !v)}
          className="btn-gold px-5 py-2 text-sm"
        >
          {showForm ? 'Cancel' : '+ Add Key'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleAdd} className="bg-surface border border-gray-800 rounded-xl p-6 mb-6">
          <h2 className="text-white font-semibold mb-4">Add New API Key</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Label</label>
              <input
                type="text"
                placeholder="e.g. Key 1, Personal, Backup"
                value={form.label}
                onChange={e => setForm(f => ({ ...f, label: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Provider</label>
              <select
                value={form.provider}
                onChange={e => setForm(f => ({ ...f, provider: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-amber-500"
              >
                <option value="gemini">Gemini</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">API Key</label>
              <input
                type="password"
                placeholder="AIza..."
                value={form.api_key}
                onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                className="w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-amber-500 font-mono"
              />
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <button type="submit" disabled={adding} className="btn-gold px-6 py-2 text-sm">
              {adding ? 'Adding...' : 'Add Key'}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-6 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : keys.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-5xl mb-4">🔑</p>
          <p className="text-gray-400 text-lg">No API keys added yet.</p>
          <p className="text-gray-500 text-sm mt-2">Add a Gemini API key to use it for AI candidate analysis.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {keys.map(key => {
            const limited = isRateLimited(key)
            return (
              <div
                key={key.id}
                className={`bg-surface border rounded-xl p-5 flex items-center justify-between gap-4 ${
                  limited ? 'border-red-500/30' : 'border-gray-800'
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-white font-semibold">{key.label}</span>
                    <span className="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded-full">
                      {key.provider}
                    </span>
                    {limited ? (
                      <span className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full">
                        🔴 Rate Limited
                      </span>
                    ) : (
                      <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full">
                        🟢 Available
                      </span>
                    )}
                  </div>
                  <p className="text-gray-500 text-xs font-mono">{key.masked_key}</p>
                  {limited && key.rate_limited_until && (
                    <p className="text-red-400 text-xs mt-1">
                      Resets at {new Date(key.rate_limited_until).toLocaleString()}
                    </p>
                  )}
                  <p className="text-gray-600 text-xs mt-1">
                    Added {new Date(key.created_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {limited && (
                    <button
                      onClick={() => handleClearLimit(key.id)}
                      disabled={clearingId === key.id}
                      className="text-xs text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 px-3 py-1.5 rounded-lg transition-colors"
                    >
                      {clearingId === key.id ? '...' : 'Clear Limit'}
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(key.id)}
                    disabled={deletingId === key.id}
                    className="text-xs text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    {deletingId === key.id ? '...' : 'Delete'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
