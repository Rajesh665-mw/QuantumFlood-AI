import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type { RecommendationsResponse } from '../types'
import { LoadingState, EmptyState } from '../components/LoadingState'
import RiskBadge from '../components/RiskBadge'

const PRIORITY_STYLE: Record<string, string> = {
  HIGH: 'text-risk-critical border-risk-critical/30 bg-risk-criticalBg',
  MEDIUM: 'text-risk-moderate border-risk-moderate/30 bg-risk-moderateBg',
  LOW: 'text-risk-low border-risk-low/30 bg-risk-lowBg',
}

const CATEGORY_LABELS: Record<string, string> = {
  SENSOR_DEPLOYMENT: 'Sensor Deployment',
  COMMUNICATION_SUPPORT: 'Communication Support',
  COVERAGE_GAP: 'Coverage Gap',
  STATUS: 'System Status',
}

export default function DisasterResponse() {
  const [data, setData] = useState<RecommendationsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [errored, setErrored] = useState(false)

  useEffect(() => {
    api.recommendations()
      .then(setData)
      .catch(() => setErrored(true))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingState label="Compiling recommendations…" />

  return (
    <div className="flex flex-col gap-8">
      <div>
        <span className="eyebrow">Module 9 · Disaster Response Recommendation Engine</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Disaster Response</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          Transparent, rule-based recommendations generated from the current forecast, risk zones,
          sensor placement, and connectivity results — every message traces back to a specific
          IF/THEN rule evaluated against real pipeline output.
        </p>
      </div>

      {errored || !data ? (
        <EmptyState
          title="No recommendations yet"
          description="Run the pipeline (forecast → risk generation → sensor optimisation) to generate response recommendations."
        />
      ) : (
        <>
          {data.alerts.length > 0 && (
            <div className="panel p-5">
              <span className="data-label">Critical Alerts</span>
              <div className="flex flex-col gap-2 mt-3">
                {data.alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-base-700 rounded">
                    <RiskBadge level={a.level} size="sm" />
                    <p className="text-ink-300 text-sm">{a.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="panel p-5">
            <span className="data-label">Priority Monitoring Areas</span>
            <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mt-3">
              {data.priority_monitoring_areas.map((z) => (
                <div key={z.zone_id} className="bg-base-700 rounded p-3">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-sm text-ink-100">{z.zone_id}</span>
                    <RiskBadge level={z.risk_level} size="sm" />
                  </div>
                  <div className="text-ink-700 text-xs mt-1 font-mono">
                    {z.centroid.lat.toFixed(3)}, {z.centroid.lon.toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel p-5">
            <span className="data-label">Recommended Actions</span>
            {data.recommendations.length === 0 ? (
              <p className="text-risk-low text-sm mt-3">No outstanding actions — current deployment satisfies all rules.</p>
            ) : (
              <div className="flex flex-col gap-2 mt-3">
                {data.recommendations.map((r, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-base-700 rounded">
                    <span className={`font-mono text-[10px] uppercase px-2 py-1 rounded border shrink-0 mt-0.5 ${PRIORITY_STYLE[r.priority]}`}>
                      {r.priority}
                    </span>
                    <div>
                      <span className="data-label">{CATEGORY_LABELS[r.category] ?? r.category}</span>
                      <p className="text-ink-100 text-sm mt-1">{r.message}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
