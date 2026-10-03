import type { ReactNode } from 'react'

export default function StatCard({
  label, value, unit, sublabel, accent,
}: {
  label: string
  value: string | number
  unit?: string
  sublabel?: string
  accent?: 'teal' | 'low' | 'moderate' | 'high' | 'critical'
}) {
  const accentColor: Record<string, string> = {
    teal: 'text-signal-teal',
    low: 'text-risk-low',
    moderate: 'text-risk-moderate',
    high: 'text-risk-high',
    critical: 'text-risk-critical',
  }
  return (
    <div className="panel p-4 flex flex-col gap-2">
      <span className="data-label">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span className={`font-mono text-2xl font-medium ${accent ? accentColor[accent] : 'text-ink-100'}`}>
          {value}
        </span>
        {unit && <span className="text-ink-500 text-sm">{unit}</span>}
      </div>
      {sublabel && <span className="text-ink-500 text-xs">{sublabel}</span>}
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="panel p-4 flex flex-col gap-2 animate-pulse">
      <div className="h-3 w-20 bg-base-600 rounded" />
      <div className="h-7 w-16 bg-base-600 rounded" />
    </div>
  )
}

export function InlineIcon({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center justify-center">{children}</span>
}
