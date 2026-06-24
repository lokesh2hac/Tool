export default function Toast({ message, type = 'success' }) {
  const colors = type === 'success'
    ? 'bg-green-500/20 border-green-500/40 text-green-300'
    : 'bg-red-500/20 border-red-500/40 text-red-300'

  const icon = type === 'success' ? '✅' : '❌'

  return (
    <div className="fixed top-4 right-4 z-[100] animate-fade-in">
      <div className={`flex items-center gap-3 px-5 py-3 rounded-xl border backdrop-blur-sm shadow-lg ${colors}`}>
        <span>{icon}</span>
        <p className="text-sm font-medium">{message}</p>
      </div>
    </div>
  )
}
