import RiskBadge from '../RiskBadge'
import { RISK_COLORS } from './baseLayers'

export default function RiskLegend({ riverName }: { riverName?: string }) {
  return (
    <div className="panel p-4 flex flex-wrap items-center gap-4">
      <span className="data-label">Legend</span>
      {(['LOW', 'MODERATE', 'HIGH', 'CRITICAL'] as const).map((lvl) => (
        <div key={lvl} className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: RISK_COLORS[lvl] }} />
          <RiskBadge level={lvl} size="sm" />
        </div>
      ))}
      {riverName && (
        <div className="flex items-center gap-2 ml-4">
          <span className="w-4 h-0.5 bg-[#3B82C4]" />
          <span className="text-xs text-ink-500">{riverName}</span>
        </div>
      )}
    </div>
  )
}
