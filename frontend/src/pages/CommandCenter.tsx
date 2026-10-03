import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../services/api'
import type { DashboardSummary } from '../types'
import StatCard, { StatCardSkeleton } from '../components/StatCard'
import RiskBadge from '../components/RiskBadge'
import { ErrorState } from '../components/LoadingState'

export default function CommandCenter() {
  const [data, setData] = useState<DashboardSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.dashboardSummary()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load dashboard.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="flex flex-col gap-8">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <span className="eyebrow">System Status &amp; Rollup</span>
          <h1 className="font-display text-2xl text-ink-100 mt-1">Command Center</h1>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-ink-500">
          <span className="w-2 h-2 rounded-full bg-signal-teal animate-pulse" />
          SYSTEM ONLINE · CORRIDOR BASELINE
        </div>
      </div>

      {error && <ErrorState message={error} />}

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <StatCardSkeleton key={i} />)}
        </div>
      ) : data ? (
        <>
          <div className="panel p-5">
            <span className="data-label">Selected Study Area</span>
            <h2 className="font-display text-xl text-ink-100 mt-1">{data.study_area.name}</h2>
            <p className="text-ink-500 text-sm mt-1">{data.study_area.state} · within the {data.study_area.basin ?? data.study_area.region}</p>
            {data.study_area.scope_note && (
              <p className="text-ink-700 text-xs mt-2 max-w-2xl">{data.study_area.scope_note}</p>
            )}
          </div>

          {!data.risk_available && !data.optimization_available && (
            <div className="panel p-6 border-signal-tealDim/40">
              <p className="text-ink-300 text-sm">
                No forecast or risk data has been generated yet this session. Start the pipeline from{' '}
                <Link to="/forecasting" className="text-signal-teal underline">Flood Forecasting</Link> or run{' '}
                <Link to="/scenario-comparison" className="text-signal-teal underline">Flood Scenarios</Link>.
              </p>
            </div>
          )}

          {/* Key Metric Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="panel p-4 flex flex-col gap-2">
              <span className="data-label">Current Risk</span>
              {data.base_risk ? (
                <RiskBadge level={data.base_risk.overall_risk} />
              ) : (
                <span className="text-ink-700 text-sm">Not generated</span>
              )}
            </div>
            <StatCard
              label="Critical Zones"
              value={data.critical_zone_count ?? '—'}
              accent="critical"
            />
            <StatCard
              label="High-Risk Zones"
              value={data.high_zone_count ?? '—'}
              accent="high"
            />
            <StatCard
              label="Latest Forecast"
              value={data.latest_forecast ? data.latest_forecast.predicted_water_level_m : '—'}
              unit={data.latest_forecast ? 'm' : undefined}
              sublabel={data.latest_forecast ? `+${data.latest_forecast.horizon_days}d · ${data.latest_forecast.model_used}` : 'Not run'}
              accent="teal"
            />
            <StatCard
              label="Sensors Deployed"
              value={data.optimization?.num_sensors_selected ?? '—'}
            />
            <StatCard
              label="Total Coverage"
              value={data.optimization?.coverage_percentage ?? '—'}
              unit={data.optimization ? '%' : undefined}
              accent="teal"
            />
            <StatCard
              label="Comm Nodes"
              value={data.connectivity?.comm_nodes.length ?? '—'}
            />
            <StatCard
              label="Connectivity"
              value={data.connectivity?.connectivity_percentage ?? '—'}
              unit={data.connectivity ? '%' : undefined}
              accent={data.connectivity && data.connectivity.connectivity_percentage < 100 ? 'moderate' : 'low'}
            />
          </div>

          {/* Tactical Modules Launcher Grid */}
          <div className="panel p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-base-600/60 pb-2">
              <span className="data-label">Disaster Decision-Support Suite</span>
              <span className="font-mono text-[11px] text-signal-teal">6 ACTIVE MODULES</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
              <Link
                to="/safe-locations"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 1</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Safe Location Finder
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Multi-criteria lower-risk public assembly sites &amp; camps.
                </p>
              </Link>

              <Link
                to="/evacuation-routing"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 2</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Evacuation Routing
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Risk-penalised routing steering away from riverfront flood corridors.
                </p>
              </Link>

              <Link
                to="/adaptive-redeployment"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 3</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Adaptive Redeployment
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Sensor transitions (KEEP, RELOCATE, ADD, REMOVE) under risk shifts.
                </p>
              </Link>

              <Link
                to="/network-resilience"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 4</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Network Resilience
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Node failure simulation, partition metrics &amp; recovery relay planning.
                </p>
              </Link>

              <Link
                to="/resource-allocation"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 5</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Resource Allocation
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Constrained distribution of rescue squads, medical units, and vehicles.
                </p>
              </Link>

              <Link
                to="/scenario-comparison"
                className="p-3 bg-base-900/60 border border-base-700 hover:border-signal-teal rounded transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase">Module 6</span>
                  <span className="text-ink-500 group-hover:text-signal-teal transition-colors">→</span>
                </div>
                <div className="font-display font-semibold text-sm text-ink-100 mt-1">
                  Scenario Simulator
                </div>
                <p className="text-xs text-ink-400 mt-1">
                  Multi-scenario pipeline comparison &amp; cross-system active state propagation.
                </p>
              </Link>
            </div>
          </div>

          {/* Key Alerts */}
          {data.recommendations && data.recommendations.alerts.length > 0 && (
            <div className="panel p-5">
              <span className="data-label">Key Alerts</span>
              <div className="flex flex-col gap-2 mt-3">
                {data.recommendations.alerts.map((a, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-base-700 rounded">
                    <RiskBadge level={a.level} size="sm" />
                    <p className="text-ink-300 text-sm">{a.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommended Actions */}
          {data.recommendations && data.recommendations.recommendations.length > 0 && (
            <div className="panel p-5">
              <span className="data-label">Top Recommended Actions</span>
              <div className="flex flex-col gap-2 mt-3">
                {data.recommendations.recommendations.slice(0, 4).map((r, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 bg-base-700 rounded">
                    <span className={`font-mono text-[10px] uppercase px-1.5 py-0.5 rounded border shrink-0 mt-0.5 ${
                      r.priority === 'HIGH' ? 'text-risk-critical border-risk-critical/30' :
                      r.priority === 'MEDIUM' ? 'text-risk-moderate border-risk-moderate/30' :
                      'text-risk-low border-risk-low/30'
                    }`}>{r.priority}</span>
                    <p className="text-ink-300 text-sm">{r.message}</p>
                  </div>
                ))}
              </div>
              <Link to="/disaster-response" className="inline-block text-signal-teal text-xs font-mono mt-3 hover:underline">
                View all recommendations →
              </Link>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
