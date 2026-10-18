import React from 'react'

export type MapScanStage =
  | 'idle'
  | 'placeholder'
  | 'scanning'
  | 'area-found'
  | 'tiles-loading'
  | 'flying-to-area'
  | 'ready'
  | 'error'

export interface MapScannerProps {
  stage: MapScanStage
  locationName?: string
  coordinates?: { lat: number; lon: number } | null
  boundsSummary?: string | null
  errorMessage?: string | null
  onRetry?: () => void
  onResetBenchmark?: () => void
  onReady?: () => void
}

export default function MapScanner({
  stage,
  locationName = 'Active Study Area',
  coordinates,
  boundsSummary,
  errorMessage,
  onRetry,
  onResetBenchmark,
  onReady,
}: MapScannerProps) {
  // Guarantee that MapScanner completely disappears after flight/tile loading finishes
  React.useEffect(() => {
    if (stage === 'flying-to-area' || stage === 'tiles-loading') {
      const timer = setTimeout(() => {
        onReady?.()
      }, 750)
      return () => clearTimeout(timer)
    }
  }, [stage, onReady])

  if (stage === 'ready' || stage === 'idle') {
    return null
  }

  const isFading = stage === 'tiles-loading' || stage === 'flying-to-area'

  return (
    <div
      className={`absolute inset-0 z-[500] flex flex-col items-center justify-center overflow-hidden transition-all duration-300 pointer-events-none ${
        isFading
          ? 'bg-transparent opacity-0 pointer-events-none'
          : 'bg-base-950/90 pointer-events-auto'
      }`}
      role="status"
      aria-live="polite"
      aria-label={`Map loading status: ${stage}`}
    >
      {/* Background GIS Coordinate Grid and Vignette — only during initial scanning stages, never during map display */}
      {!isFading && (
        <>
          <div className="absolute inset-0 map-scanner-grid opacity-30 pointer-events-none" />
          <div className="absolute inset-0 map-scanner-vignette pointer-events-none" />
        </>
      )}

      {/* Decorative Subtle Terrain Contours SVG */}
      <svg
        className="absolute inset-0 w-full h-full opacity-15 pointer-events-none"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="none"
        viewBox="0 0 800 500"
      >
        <path
          d="M0,250 C150,180 250,320 400,240 C550,160 650,280 800,220"
          fill="none"
          stroke="#2DD4BF"
          strokeWidth="1.2"
          strokeDasharray="4 6"
        />
        <path
          d="M0,290 C180,220 280,360 430,270 C580,180 680,310 800,260"
          fill="none"
          stroke="#2DD4BF"
          strokeWidth="0.8"
        />
        <path
          d="M0,330 C200,260 300,400 460,300 C620,200 700,340 800,300"
          fill="none"
          stroke="#2DD4BF"
          strokeWidth="0.6"
          strokeDasharray="2 4"
        />
      </svg>

      {/* Four Precision HUD Corner Brackets */}
      <div className="absolute top-3 left-3 w-6 h-6 border-t-2 border-l-2 hud-corner pointer-events-none" />
      <div className="absolute top-3 right-3 w-6 h-6 border-t-2 border-r-2 hud-corner pointer-events-none" />
      <div className="absolute bottom-3 left-3 w-6 h-6 border-b-2 border-l-2 hud-corner pointer-events-none" />
      <div className="absolute bottom-3 right-3 w-6 h-6 border-b-2 border-r-2 hud-corner pointer-events-none" />

      {/* Top Header Readout */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 px-3 py-1 bg-base-900/80 border border-base-700/80 rounded-full text-[11px] font-mono text-ink-400 shadow-md">
        <span className="w-2 h-2 rounded-full bg-signal-teal animate-pulse" />
        <span className="uppercase tracking-widest text-[10px] text-ink-300">
          Geospatial Grid Calibration
        </span>
      </div>

      {/* ========================================================= */}
      {/* STAGE A: PLACEHOLDER */}
      {/* ========================================================= */}
      {stage === 'placeholder' && (
        <div className="relative z-10 flex flex-col items-center gap-3 text-center px-4 animate-fade-in">
          <div className="relative w-14 h-14 flex items-center justify-center">
            <span className="absolute inset-0 rounded-full border border-signal-teal/30 animate-ping opacity-30" />
            <span className="w-10 h-10 rounded-full border border-signal-teal/60 flex items-center justify-center bg-base-900/80 shadow-[0_0_15px_rgba(45,212,191,0.2)]">
              <span className="w-3 h-3 rounded-full bg-signal-teal animate-pulse" />
            </span>
          </div>
          <div>
            <div className="font-display font-semibold text-ink-100 text-base tracking-tight">
              Preparing Study Area
            </div>
            <div className="font-mono text-xs text-ink-400 mt-1">
              Initializing spatial bounds &amp; river basin coordinates…
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* STAGE B: SCANNING (MAGNIFYING GLASS SWEEP) */}
      {/* ========================================================= */}
      {stage === 'scanning' && (
        <>
          {/* Sweeping Magnifying Glass within Viewport */}
          <div className="absolute z-10 pointer-events-none animate-glass-sweep -translate-x-1/2 -translate-y-1/2">
            {/* Scanning Light Beam Cone */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 pointer-events-none animate-beam-cone">
              <div
                className="w-full h-full rounded-full"
                style={{
                  background:
                    'radial-gradient(circle, rgba(45,212,191,0.25) 0%, rgba(45,212,191,0.06) 45%, transparent 70%)',
                }}
              />
            </div>

            {/* Magnifying Glass SVG */}
            <div className="relative w-20 h-20 filter drop-shadow-[0_0_12px_rgba(45,212,191,0.5)]">
              <svg viewBox="0 0 80 80" className="w-full h-full" fill="none">
                {/* Circular Glass Lens with Reticle */}
                <circle
                  cx="34"
                  cy="34"
                  r="24"
                  className="stroke-signal-teal"
                  strokeWidth="2.5"
                  fill="rgba(11, 25, 38, 0.55)"
                />
                {/* Crosshairs inside lens */}
                <line
                  x1="34"
                  y1="16"
                  x2="34"
                  y2="24"
                  className="stroke-signal-teal"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <line
                  x1="34"
                  y1="44"
                  x2="34"
                  y2="52"
                  className="stroke-signal-teal"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <line
                  x1="16"
                  y1="34"
                  x2="24"
                  y2="34"
                  className="stroke-signal-teal"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <line
                  x1="44"
                  y1="34"
                  x2="52"
                  y2="34"
                  className="stroke-signal-teal"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <circle cx="34" cy="34" r="2" className="fill-signal-teal" />

                {/* Angled Handle */}
                <path
                  d="M51 51 L68 68"
                  className="stroke-signal-teal"
                  strokeWidth="5"
                  strokeLinecap="round"
                />
                <path
                  d="M51 51 L68 68"
                  className="stroke-base-950"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            </div>

            {/* Coordinate readout HUD directly under magnifying glass */}
            <div className="absolute top-full left-1/2 -translate-x-1/2 mt-1 whitespace-nowrap bg-base-950/90 border border-signal-teal/40 rounded px-2 py-0.5 text-[10px] font-mono text-signal-teal shadow-lg">
              {coordinates
                ? `SCANNING ${coordinates.lat.toFixed(3)}°, ${coordinates.lon.toFixed(3)}°`
                : 'SCANNING VECTOR GRID…'}
            </div>
          </div>

          {/* Bottom Floating Live Status Pill */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2.5 bg-base-950/90 backdrop-blur-md border border-signal-teal/50 rounded-full px-4 py-2 shadow-2xl">
            <span className="w-2.5 h-2.5 rounded-full bg-signal-teal status-glow shrink-0" />
            <span className="font-mono text-xs text-signal-teal uppercase tracking-wider whitespace-nowrap">
              Searching for your area… ({locationName})
            </span>
          </div>
        </>
      )}

      {/* ========================================================= */}
      {/* STAGE C: AREA FOUND (LOCK-ON & VALIDATION CONFIRMATION) */}
      {/* ========================================================= */}
      {stage === 'area-found' && (
        <div className="relative z-20 flex flex-col items-center gap-3 max-w-md mx-4 animate-lockon">
          {/* Target Reticle with Expanding Brackets */}
          <div className="relative w-16 h-16 flex items-center justify-center">
            <span className="absolute inset-0 rounded-full border-2 border-signal-teal/40 animate-ping opacity-40" />
            <div className="w-14 h-14 rounded-full border-2 border-signal-teal bg-base-900/90 flex items-center justify-center shadow-[0_0_24px_rgba(45,212,191,0.4)]">
              {/* Checkmark icon */}
              <svg className="w-7 h-7 text-signal-teal" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
              </svg>
            </div>
          </div>

          {/* Area Confirmation Card */}
          <div className="bg-base-900/95 border border-signal-teal/50 rounded-lg p-4 text-center shadow-2xl w-full">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/30 font-mono text-[10px] uppercase tracking-wider font-semibold mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-signal-teal" />
              Area Found &amp; Validated
            </div>
            <h3 className="font-display text-lg text-ink-100 font-bold tracking-tight">
              {locationName}
            </h3>
            {coordinates && (
              <div className="mt-2 font-mono text-xs text-ink-300 flex items-center justify-center gap-3">
                <span className="text-signal-teal">
                  {coordinates.lat.toFixed(4)}° N, {coordinates.lon.toFixed(4)}° E
                </span>
                {boundsSummary && (
                  <span className="text-ink-500 text-[11px]">
                    · {boundsSummary}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* STAGE D: TILES LOADING */}
      {/* ========================================================= */}
      {stage === 'tiles-loading' && (
        <div className="relative z-20 flex flex-col items-center gap-3 bg-base-950/85 backdrop-blur-md border border-signal-teal/40 rounded-xl px-6 py-4 shadow-2xl animate-fade-in">
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-signal-teal animate-ping" />
            <span className="font-mono text-xs text-ink-100 uppercase tracking-wider font-medium">
              Loading Map Tiles &amp; Cartography…
            </span>
          </div>
          {/* Indeterminate loading bar */}
          <div className="w-56 h-1.5 bg-base-800 rounded-full overflow-hidden relative">
            <div className="absolute top-0 bottom-0 left-0 w-24 bg-signal-teal rounded-full animate-indeterminate shadow-[0_0_8px_rgba(45,212,191,0.8)]" />
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* STAGE E: FLYING TO AREA */}
      {/* ========================================================= */}
      {stage === 'flying-to-area' && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-base-950/85 backdrop-blur-md border border-signal-teal/30 rounded-full px-4 py-1.5 shadow-lg">
          <span className="w-2 h-2 rounded-full bg-signal-teal animate-pulse" />
          <span className="font-mono text-[11px] text-ink-200 uppercase tracking-wider">
            Zooming into study area…
          </span>
        </div>
      )}

      {/* ========================================================= */}
      {/* ERROR STATE */}
      {/* ========================================================= */}
      {stage === 'error' && (
        <div className="relative z-20 flex flex-col items-center gap-3 bg-base-900/95 border border-risk-critical/60 rounded-lg p-6 max-w-md mx-4 text-center shadow-2xl animate-fade-in">
          <div className="w-10 h-10 rounded-full bg-risk-critical/20 border border-risk-critical flex items-center justify-center text-risk-critical font-bold text-lg">
            ✕
          </div>
          <h3 className="font-display text-base text-ink-100 font-semibold">
            Study Area Geocoding Failed
          </h3>
          <p className="text-xs text-ink-400">
            {errorMessage || 'Unable to resolve the requested study area or load map boundary tiles.'}
          </p>
          <div className="flex items-center gap-2 mt-2">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="bg-signal-teal text-base-950 font-medium px-4 py-1.5 rounded text-xs hover:bg-signal-teal/90 transition-colors"
              >
                Retry Search
              </button>
            )}
            {onResetBenchmark && (
              <button
                type="button"
                onClick={onResetBenchmark}
                className="border border-base-600 text-ink-200 px-3 py-1.5 rounded text-xs hover:bg-base-800 transition-colors"
              >
                Revert to Vijayawada Benchmark
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
