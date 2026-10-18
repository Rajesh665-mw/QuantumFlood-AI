import React from 'react'

export function LoadingState({
  label = 'Loading system data…',
  sublabel = 'Synchronizing hydrological & quantum intelligence pipeline',
}: {
  label?: string
  sublabel?: string
}) {
  return (
    <div
      className="panel p-8 max-w-md mx-auto my-12 flex flex-col items-center justify-center text-center bg-base-900/80 border border-base-750 rounded-xl shadow-xl page-enter relative overflow-hidden"
      role="status"
      aria-live="polite"
    >
      {/* Subtle ambient background glow */}
      <div className="absolute inset-0 bg-radial-gradient pointer-events-none opacity-30" />

      {/* Branded Radar / Hydrological Wave Motif */}
      <div className="relative w-16 h-16 mb-4 flex items-center justify-center">
        {/* Outer pulsing ring */}
        <span className="absolute inset-0 rounded-full border border-signal-teal/30 animate-ping opacity-25" />
        {/* Middle radar circle */}
        <div className="w-12 h-12 rounded-full border border-signal-teal/50 bg-base-950/80 flex items-center justify-center shadow-[0_0_16px_rgba(45,212,191,0.25)]">
          {/* Inner core node */}
          <span className="w-3.5 h-3.5 rounded-full bg-signal-teal animate-pulse" />
        </div>
      </div>

      {/* Label and Sublabel */}
      <h4 className="font-display font-semibold text-ink-100 text-sm tracking-tight">
        {label}
      </h4>
      <p className="font-mono text-[11px] text-ink-500 mt-1 max-w-xs leading-relaxed">
        {sublabel}
      </p>

      {/* Restrained Indeterminate Signal Line */}
      <div className="w-48 h-1 bg-base-800 rounded-full overflow-hidden mt-4 relative">
        <div className="absolute top-0 bottom-0 left-0 w-20 bg-signal-teal rounded-full animate-indeterminate shadow-[0_0_8px_rgba(45,212,191,0.7)]" />
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="panel flex flex-col items-center justify-center gap-3 py-16 px-6 text-center fade-in bg-base-900/60 border border-base-750">
      <h3 className="font-display text-lg text-ink-100 font-semibold">{title}</h3>
      <p className="text-ink-500 text-sm max-w-md">{description}</p>
      {action}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="panel border-risk-critical/40 bg-risk-criticalBg/40 p-5 text-sm scale-in rounded-lg">
      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-risk-critical" />
        <span className="font-mono text-risk-critical uppercase tracking-wider text-xs font-semibold">
          Execution Error
        </span>
      </div>
      <p className="text-ink-100 mt-1.5 text-xs font-mono">{message}</p>
    </div>
  )
}

/** Full-page dashboard skeleton — used while route modules lazy-load */
export function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6 page-enter" role="status" aria-label="Loading page content">
      {/* Header skeleton */}
      <div className="flex flex-col gap-2">
        <div className="skeleton-shimmer h-3 w-32 rounded" />
        <div className="skeleton-shimmer h-7 w-64 rounded" />
        <div className="skeleton-shimmer h-4 w-96 mt-1 rounded" />
      </div>
      {/* Stat cards skeleton */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="panel p-4 flex flex-col gap-3 border border-base-750">
            <div className="skeleton-shimmer h-3 w-20 rounded" />
            <div className="skeleton-shimmer h-7 w-14 rounded" />
          </div>
        ))}
      </div>
      {/* Content skeleton */}
      <div className="panel p-6 flex flex-col gap-3 border border-base-750">
        <div className="skeleton-shimmer h-4 w-48 rounded" />
        <div className="skeleton-shimmer h-3 w-full rounded" />
        <div className="skeleton-shimmer h-3 w-4/5 rounded" />
        <div className="skeleton-shimmer h-3 w-3/5 rounded" />
      </div>
    </div>
  )
}

/** Map placeholder skeleton — dark GIS themed viewport skeleton */
export function MapSkeleton({ height = '520px' }: { height?: string }) {
  return (
    <div
      className="panel overflow-hidden relative border border-base-700/80 bg-base-950 flex flex-col items-center justify-center"
      style={{ height }}
      role="status"
      aria-label="Loading map coordinates"
    >
      {/* Coordinate grid background */}
      <div className="absolute inset-0 map-scanner-grid opacity-60" />

      {/* Four precision corner brackets */}
      <div className="absolute top-3 left-3 w-5 h-5 border-t-2 border-l-2 border-signal-teal/40 pointer-events-none" />
      <div className="absolute top-3 right-3 w-5 h-5 border-t-2 border-r-2 border-signal-teal/40 pointer-events-none" />
      <div className="absolute bottom-3 left-3 w-5 h-5 border-b-2 border-l-2 border-signal-teal/40 pointer-events-none" />
      <div className="absolute bottom-3 right-3 w-5 h-5 border-b-2 border-r-2 border-signal-teal/40 pointer-events-none" />

      {/* Center status */}
      <div className="relative z-10 flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full border border-signal-teal/50 bg-base-900/80 flex items-center justify-center shadow-[0_0_15px_rgba(45,212,191,0.2)]">
          <span className="w-3 h-3 rounded-full bg-signal-teal animate-pulse" />
        </div>
        <span className="font-mono text-xs text-ink-400 uppercase tracking-wider">
          Initializing Spatial Boundary Layers…
        </span>
      </div>
    </div>
  )
}

/** Generic content block skeleton */
export function ContentSkeleton({ lines = 4 }: { lines?: number }) {
  return (
    <div className="panel p-5 flex flex-col gap-2.5 fade-in border border-base-750">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton-shimmer h-3 rounded"
          style={{ width: `${90 - i * 12}%` }}
        />
      ))}
    </div>
  )
}

/** Panel-shaped skeleton with configurable rows */
export function PanelSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="panel p-5 flex flex-col gap-3 border border-base-750">
      <div className="skeleton-shimmer h-4 w-36 rounded" />
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="skeleton-shimmer h-3 rounded"
          style={{ width: `${95 - i * 15}%` }}
        />
      ))}
    </div>
  )
}
