import type { RiskLevel } from '../types'

const STYLES: Record<RiskLevel, string> = {
  LOW: 'text-risk-low bg-risk-lowBg border-risk-low/30',
  MODERATE: 'text-risk-moderate bg-risk-moderateBg border-risk-moderate/30',
  HIGH: 'text-risk-high bg-risk-highBg border-risk-high/30',
  CRITICAL: 'text-risk-critical bg-risk-criticalBg border-risk-critical/30',
}

export default function RiskBadge({ level, size = 'md' }: { level: RiskLevel; size?: 'sm' | 'md' }) {
  const sizeCls = size === 'sm' ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2 py-1'
  return (
    <span className={`inline-flex items-center gap-1.5 font-mono uppercase tracking-wider border rounded ${sizeCls} ${STYLES[level]}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {level}
    </span>
  )
}
