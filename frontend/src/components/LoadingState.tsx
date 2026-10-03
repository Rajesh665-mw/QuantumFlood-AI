export function LoadingState({ label = 'Loading system data…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-ink-500">
      <div className="w-8 h-8 border-2 border-base-600 border-t-signal-teal rounded-full animate-spin" />
      <span className="font-mono text-xs uppercase tracking-wider">{label}</span>
    </div>
  )
}

export function EmptyState({
  title, description, action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="panel flex flex-col items-center justify-center gap-3 py-16 px-6 text-center">
      <h3 className="font-display text-lg text-ink-100">{title}</h3>
      <p className="text-ink-500 text-sm max-w-md">{description}</p>
      {action}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="panel border-risk-critical/40 bg-risk-criticalBg/40 p-4 text-sm">
      <span className="font-mono text-risk-critical uppercase tracking-wider text-xs">Error</span>
      <p className="text-ink-100 mt-1">{message}</p>
    </div>
  )
}
