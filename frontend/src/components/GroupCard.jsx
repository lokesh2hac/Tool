export default function GroupCard({ group, selected, onToggle }) {
  const memberCount = group.member_count
    ? group.member_count.toLocaleString()
    : 'Unknown'

  return (
    <div
      onClick={onToggle}
      className={`cursor-pointer rounded-xl border p-4 transition-all duration-200 ${
        selected
          ? 'border-amber-500 bg-amber-500/10 shadow-lg shadow-amber-500/10'
          : 'border-gray-800 bg-surface hover:border-gray-600 hover:bg-gray-800/50'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold text-sm truncate">{group.group_title}</h3>
          {group.group_username && (
            <p className="text-amber-400 text-xs mt-0.5">@{group.group_username}</p>
          )}
        </div>
        <div className={`w-5 h-5 rounded border-2 flex-shrink-0 flex items-center justify-center transition-colors ${
          selected ? 'border-amber-500 bg-amber-500' : 'border-gray-600'
        }`}>
          {selected && <span className="text-gray-900 text-xs font-bold">✓</span>}
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3 text-xs text-gray-500">
        <span>👥 {memberCount} members</span>
        {group.keyword && <span>🔑 {group.keyword}</span>}
      </div>

      {group.description && (
        <p className="text-gray-400 text-xs mt-2 line-clamp-2">{group.description}</p>
      )}
    </div>
  )
}
