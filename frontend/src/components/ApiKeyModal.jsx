import { useState, useEffect } from 'react'
import api from '../api'

export default function ApiKeyModal({ rateLimitedKeyId, onKeySelected, onClose }) {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [clearingId, setClearingId] = useState(null)

  const fetchKeys = () => {
    setLoading(true)
    api.get('/api/api-keys')
      .then(res => setKeys(res.data || []))
      .catch(() => setKeys([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchKeys()
    // Auto-mark the rate-limited key in the backend
    if (rateLimitedKeyId) {
      api.post(`/api/api-keys/${rateLimitedKeyId}/mark-rate-limited`).catch(() => {})
    }
  }, [rateLimitedKeyId])

  const isRateLimited = (key) => {
    if (!key.rate_limited_until) return false
    return new Date(key.rate_limited_until) > new Date()
  }

  const handleClearLimit = async (keyId) => {
    setClearingId(keyId)
    try {
      await api.post(`/api/api-keys/${keyId}/clear-rate-limit`)
      fetchKeys()
    } catch {
      // ignore
    } finally {
      setClearingId(null)
    }
  }

  const availableKeys = keys.filter(k => k.is_active && !isRateLimited(k))

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-gray-800 rounded-2xl w-full max-w-lg shadow-2xl">
        <div className="p-6 border-b border-gray-800">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-2xl">⚠️</span>
            <h3 className="text-white font-bold text-lg">Gemini Rate Limit Hit</h3>
          </div>
          <p className="text-gray-400 text-sm mt-1">
            The current API key has been rate limited. Select a different available key to continue.
          </p>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-8 h-8 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : keys.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-gray-400">No API keys configured.</p>
              <p className="text-gray-500 text-sm mt-1">
                Go to <span className="text-amber-400">API Keys</span> in the navbar to add keys.
              </p>
            </div>
          ) : (
            <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
              {keys.map(key => {
                const limited = isRateLimited(key)
                const isCurrentLimited = key.id === rateLimitedKeyId
                return (
                  <div
                    key={key.id}
                    className={`flex items-center justify-between p-4 rounded-xl border transition-colors ${
                      limited
                        ? 'border-red-500/30 bg-red-500/5 opacity-60'
                        : 'border-gray-700 bg-gray-800/50 hover:border-amber-500/50 cursor-pointer'
                    }`}
                    onClick={() => !limited && onKeySelected(key)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium text-sm truncate">{key.label}</span>
                        {isCurrentLimited && (
                          <span className="text-xs bg-red-500/20 text-red-400 border border-red-500/30 px-2 py-0.5 rounded-full">
                            Current
                          </span>
                        )}
                      </div>
                      <p className="text-gray-500 text-xs font-mono mt-0.5">{key.masked_key}</p>
                      {limited && key.rate_limited_until && (
                        <p className="text-red-400 text-xs mt-1">
                          Rate limited until {new Date(key.rate_limited_until).toLocaleTimeString()}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                      {limited ? (
                        <>
                          <span className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-1 rounded-lg">
                            🔴 Limited
                          </span>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleClearLimit(key.id) }}
                            disabled={clearingId === key.id}
                            className="text-xs text-gray-400 hover:text-white bg-gray-700 hover:bg-gray-600 px-2 py-1 rounded-lg transition-colors"
                          >
                            {clearingId === key.id ? '...' : 'Clear'}
                          </button>
                        </>
                      ) : (
                        <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-1 rounded-lg">
                          🟢 Available
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {availableKeys.length === 0 && !loading && keys.length > 0 && (
            <p className="text-amber-400 text-sm text-center mt-4">
              All keys are rate limited. Wait for them to reset or add a new key.
            </p>
          )}
        </div>

        <div className="p-6 pt-0">
          <button
            onClick={onClose}
            className="w-full py-3 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors text-sm"
          >
            Cancel Analysis
          </button>
        </div>
      </div>
    </div>
  )
}
