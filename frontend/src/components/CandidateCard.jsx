export default function CandidateCard({ candidate, onOutreach }) {
  const scoreBg = candidate.ai_score >= 8
    ? 'from-green-500 to-emerald-600'
    : candidate.ai_score >= 6
    ? 'from-yellow-500 to-amber-600'
    : 'from-red-500 to-rose-600'

  return (
    <div className="bg-surface rounded-xl border border-gray-800 p-5 hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold">{candidate.display_name || 'Unknown'}</h3>
          <p className="text-amber-400 text-sm">{candidate.telegram_username || '—'}</p>
        </div>
        <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${scoreBg} flex items-center justify-center flex-shrink-0`}>
          <span className="text-white font-black text-lg">{candidate.ai_score}</span>
        </div>
      </div>

      {candidate.ai_reason && (
        <p className="text-gray-400 text-sm mt-3 line-clamp-2">{candidate.ai_reason}</p>
      )}

      {candidate.message_sample && (
        <div className="mt-3 bg-gray-800/50 rounded-lg p-3">
          <p className="text-gray-500 text-xs italic line-clamp-2">"{candidate.message_sample}"</p>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <span className={`text-xs px-2 py-1 rounded-full ${
          candidate.status === 'contacted'
            ? 'bg-blue-500/20 text-blue-400'
            : 'bg-gray-700 text-gray-400'
        }`}>
          {candidate.status || 'new'}
        </span>
        {candidate.status !== 'contacted' && (
          <button
            onClick={() => onOutreach(candidate)}
            className="bg-amber-500 hover:bg-amber-600 text-gray-900 text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors"
          >
            📨 Send Outreach
          </button>
        )}
      </div>
    </div>
  )
}
