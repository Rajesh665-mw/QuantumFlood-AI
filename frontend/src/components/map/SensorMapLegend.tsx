import { useState } from 'react'
import { RISK_COLORS } from './baseLayers'

interface SensorMapLegendProps {
  riverName?: string
  coverageRadiusKm?: number
  numSensorsPlaced?: number
  candidatesCount?: number
  uncoveredCount?: number
}

export default function SensorMapLegend({
  riverName = 'Study Waterway',
  coverageRadiusKm = 2.5,
  numSensorsPlaced = 0,
  candidatesCount = 0,
  uncoveredCount = 0,
}: SensorMapLegendProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="absolute bottom-3 left-3 z-[470] max-w-sm">
      <div className="bg-base-950/90 backdrop-blur-md border border-base-700/80 rounded-xl shadow-2xl overflow-hidden transition-all duration-200">
        {/* Header with collapse toggle */}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono font-semibold text-ink-200 hover:text-signal-teal transition-colors bg-base-900/60"
        >
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-signal-teal" />
            <span className="uppercase tracking-wider text-[11px]">Map Layers &amp; Symbology</span>
          </div>
          <span className="text-[10px] text-ink-500 font-mono ml-2">
            {collapsed ? '▲ Expand' : '▼ Collapse'}
          </span>
        </button>

        {!collapsed && (
          <div className="p-3 text-xs space-y-2.5 divide-y divide-base-800/80">
            {/* Optimization Symbology */}
            <div className="space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block">
                Sensor Placement Network
              </span>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="w-4 h-4 rounded-full bg-base-950 border-2 border-signal-teal text-signal-teal font-mono text-[9px] font-bold flex items-center justify-center shadow-[0_0_8px_rgba(45,212,191,0.6)]">
                    #
                  </span>
                  <span className="text-ink-200">Selected Node ({numSensorsPlaced})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3.5 h-3.5 rounded-full border border-signal-teal/70 bg-signal-teal/15" />
                  <span className="text-ink-300">Footprint ({coverageRadiusKm}km)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-sky-500" />
                  <span className="text-ink-300">Candidate Site ({candidatesCount})</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-sm border border-amber-500/80 bg-amber-500/20" />
                  <span className="text-ink-300">Uncovered Zone ({uncoveredCount})</span>
                </div>
              </div>
            </div>

            {/* Hydrology & Waterway */}
            <div className="pt-2 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block">
                Hydrological Corridor
              </span>
              <div className="flex items-center gap-2 text-[11px]">
                <span className="w-6 h-1 bg-[#3B82C4] rounded-full shadow-[0_0_6px_rgba(59,130,196,0.8)]" />
                <span className="text-ink-200 font-medium">{riverName} Centerline</span>
              </div>
            </div>

            {/* Flood Risk Levels */}
            <div className="pt-2 space-y-1.5">
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block">
                Flood Risk Classification
              </span>
              <div className="grid grid-cols-2 gap-1.5 text-[10px] font-mono">
                {(['CRITICAL', 'HIGH', 'MODERATE', 'LOW'] as const).map((lvl) => (
                  <div key={lvl} className="flex items-center gap-1.5">
                    <span
                      className="w-2.5 h-2.5 rounded-sm shrink-0"
                      style={{ backgroundColor: RISK_COLORS[lvl] }}
                    />
                    <span className="text-ink-300">
                      {lvl === 'CRITICAL' ? 'Critical (w=8.0)' :
                       lvl === 'HIGH' ? 'High (w=3.0)' :
                       lvl === 'MODERATE' ? 'Moderate (w=2.0)' : 'Low (w=1.0)'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
