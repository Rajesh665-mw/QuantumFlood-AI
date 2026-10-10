import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  Legend as RechartsLegend,
} from 'recharts'
import { api } from '../services/api'
import type {
  ScenarioComparisonResponse,
  ScenarioDefinition,
  ScenarioRunResult,
} from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { useMapLayers } from '../hooks/useMapLayers'

export default function ScenarioComparison() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<ScenarioComparisonResponse | null>(null)
  const [presets, setPresets] = useState<ScenarioDefinition[]>([])
  const [activeScenarioId, setActiveScenarioId] = useState<string>('baseline')
  const [selectedViewingScenarioId, setSelectedViewingScenarioId] = useState<string>('moderate')
  const [loading, setLoading] = useState(true)
  const [comparing, setComparing] = useState(false)
  const [activating, setActivating] = useState(false)
  const [activationMsg, setActivationMsg] = useState<string | null>(null)

  // Custom scenario fields
  const [customWaterLevel, setCustomWaterLevel] = useState(12.5)
  const [customInflow, setCustomInflow] = useState(800.0)
  const [customRainfall, setCustomRainfall] = useState(95.0)

  useEffect(() => {
    Promise.all([
      api.scenarioPresets().catch(() => ({ presets: [], active_scenario_id: 'baseline' })),
      api.compareScenarios().catch(() => null),
    ])
      .then(([presetRes, compRes]) => {
        setPresets(presetRes.presets)
        if (presetRes.active_scenario_id) {
          setActiveScenarioId(presetRes.active_scenario_id)
        }
        if (compRes) {
          setData(compRes)
          if (compRes.scenarios.length > 0) {
            setSelectedViewingScenarioId(compRes.scenarios[0].scenario_id)
          }
        }
      })
      .finally(() => setLoading(false))
  }, [])

  const handleRunComparison = async (includeCustom: boolean = false) => {
    setComparing(true)
    try {
      const scenarioList: ScenarioDefinition[] = [...presets]
      if (includeCustom) {
        scenarioList.push({
          id: 'custom_sim',
          name: 'Custom User Scenario',
          water_level_m: customWaterLevel,
          inflow_ktcmd: customInflow,
          rainfall_mm_24h: customRainfall,
          resolution: 'default',
        })
      }
      const res = await api.compareScenarios({ scenarios: scenarioList })
      setData(res)
    } catch (err) {
      console.error('Failed to run scenario comparison:', err)
    } finally {
      setComparing(false)
    }
  }

  const handleActivateScenario = async (id: string) => {
    setActivating(true)
    setActivationMsg(null)
    try {
      const custom = id === 'custom_sim' ? {
        id: 'custom_sim',
        name: 'Custom User Scenario',
        water_level_m: customWaterLevel,
        inflow_ktcmd: customInflow,
        rainfall_mm_24h: customRainfall,
        resolution: 'default'
      } : undefined

      const res = await api.activateScenario({ scenario_id: id, custom_params: custom })
      setActiveScenarioId(id)
      setActivationMsg(res.message)
      setTimeout(() => setActivationMsg(null), 6000)
    } catch (err) {
      console.error('Failed to activate scenario:', err)
    } finally {
      setActivating(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading multi-scenario simulator…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const scenarios = data?.scenarios ?? []
  const viewingScenario = scenarios.find((s) => s.scenario_id === selectedViewingScenarioId) || scenarios[0]

  const zoneRiskLookup = new Map(
    (viewingScenario?.pipeline_artifacts?.risk_map?.zones ?? []).map((z) => [z.zone_id, z])
  )

  // Chart data
  const chartData = scenarios.map((s) => ({
    name: s.name.replace(/Scenario [A-Z] — /, ''),
    Critical: s.metrics.critical_zones_count,
    High: s.metrics.high_zones_count,
    Moderate: s.metrics.moderate_zones_count,
    CoveragePct: s.metrics.sensor_coverage_percentage,
    CriticalCovPct: s.metrics.critical_zone_coverage_percentage,
  }))

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 6 · Multi-Scenario Flood Intelligence</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Multi-Scenario Flood Comparison &amp; Simulator
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Execute comparative flood scenarios through the entire QuantumFlood AI pipeline (inflow forecast →
          risk attenuation → sensor placement → network resilience → safe locations → emergency logistics).
        </p>
      </div>

      {/* Activation Feedback */}
      {activationMsg && (
        <div className="panel p-4 bg-emerald-950/40 border-emerald-500/50 text-emerald-300 text-xs font-mono flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>{activationMsg}</span>
        </div>
      )}

      {/* Preset Cards & Custom Input */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {presets.map((p) => {
          const isActive = activeScenarioId === p.id
          const isViewing = selectedViewingScenarioId === p.id
          return (
            <div
              key={p.id}
              className={`panel p-4 flex flex-col justify-between transition-all ${
                isViewing
                  ? 'border-signal-teal ring-1 ring-signal-teal/40 bg-base-800'
                  : 'hover:border-base-500 bg-base-850'
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-signal-teal uppercase tracking-wider">
                    {p.id}
                  </span>
                  {isActive && (
                    <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-300 font-mono text-[10px] rounded border border-emerald-500/40 font-bold">
                      ACTIVE
                    </span>
                  )}
                </div>
                <h3 className="font-display font-semibold text-sm text-ink-100 mt-1">{p.name}</h3>
                <p className="text-ink-400 text-xs mt-1.5 leading-relaxed">{p.description}</p>
                <div className="mt-3 pt-3 border-t border-base-700/60 font-mono text-[11px] text-ink-300 space-y-1">
                  <div>Water Level: <strong className="text-ink-100">{p.water_level_m} m</strong></div>
                  <div>Discharge: <strong className="text-ink-100">{p.inflow_ktcmd} kTCM/d</strong></div>
                  <div>Rainfall: <strong className="text-ink-100">{p.rainfall_mm_24h} mm/24h</strong></div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-base-700/60 flex items-center gap-2">
                <button
                  onClick={() => setSelectedViewingScenarioId(p.id)}
                  className={`flex-1 py-1.5 px-2 text-[11px] font-mono rounded transition-colors ${
                    isViewing
                      ? 'bg-signal-teal text-base-950 font-bold'
                      : 'bg-base-700 text-ink-200 hover:bg-base-600'
                  }`}
                >
                  {isViewing ? 'Viewing Map' : 'View on Map'}
                </button>
                <button
                  onClick={() => handleActivateScenario(p.id)}
                  disabled={activating || isActive}
                  title="Propagate this scenario through all dashboard modules"
                  className={`py-1.5 px-3 text-[11px] font-mono rounded transition-colors ${
                    isActive
                      ? 'opacity-40 cursor-not-allowed bg-base-700 text-ink-400'
                      : 'bg-base-700 hover:bg-emerald-600 hover:text-white text-ink-200'
                  }`}
                >
                  {isActive ? 'Active' : 'Set Active'}
                </button>
              </div>
            </div>
          )
        })}

        {/* Custom Scenario Card */}
        <div className="panel p-4 flex flex-col justify-between bg-base-850 border-dashed">
          <div>
            <span className="font-mono text-[10px] text-signal-teal uppercase tracking-wider">
              Custom Simulator
            </span>
            <h3 className="font-display font-semibold text-sm text-ink-100 mt-1">User Defined</h3>
            <div className="mt-3 space-y-2 font-mono text-xs">
              <div>
                <span className="text-[10px] text-ink-500 block">Water Level (m)</span>
                <input
                  type="number"
                  step="0.5"
                  value={customWaterLevel}
                  onChange={(e) => setCustomWaterLevel(parseFloat(e.target.value))}
                  className="w-full bg-base-900 border border-base-600 rounded px-2 py-1 text-ink-100"
                />
              </div>
              <div>
                <span className="text-[10px] text-ink-500 block">Inflow (kTCM/d)</span>
                <input
                  type="number"
                  step="50"
                  value={customInflow}
                  onChange={(e) => setCustomInflow(parseFloat(e.target.value))}
                  className="w-full bg-base-900 border border-base-600 rounded px-2 py-1 text-ink-100"
                />
              </div>
              <div>
                <span className="text-[10px] text-ink-500 block">Rainfall (mm/24h)</span>
                <input
                  type="number"
                  step="10"
                  value={customRainfall}
                  onChange={(e) => setCustomRainfall(parseFloat(e.target.value))}
                  className="w-full bg-base-900 border border-base-600 rounded px-2 py-1 text-ink-100"
                />
              </div>
            </div>
          </div>

          <button
            onClick={() => handleRunComparison(true)}
            disabled={comparing}
            className="w-full mt-4 py-2 px-3 bg-signal-teal text-base-950 font-display font-semibold text-xs rounded hover:bg-signal-tealDim transition-colors"
          >
            {comparing ? 'Simulating…' : 'Simulate & Compare'}
          </button>
        </div>
      </div>

      {/* Side-by-Side Comparison Table */}
      <div className="panel p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-base-600/60 pb-3">
          <div>
            <h2 className="font-display font-semibold text-sm text-ink-100">
              Cross-Scenario Performance Matrix
            </h2>
            <p className="text-ink-500 text-xs mt-0.5">
              Side-by-side evaluation of risk exposure, sensor coverage, network reliability, and relief demand.
            </p>
          </div>
          <button
            onClick={() => handleRunComparison(false)}
            disabled={comparing}
            className="py-1.5 px-3 bg-base-700 hover:bg-base-600 text-ink-200 text-xs font-mono rounded"
          >
            Refresh Matrix
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="text-ink-500 border-b border-base-600 text-left">
                <th className="py-2.5 px-3">Disaster Pipeline Metric</th>
                {scenarios.map((s) => (
                  <th key={s.scenario_id} className="py-2.5 px-3">
                    <span className="text-signal-teal font-bold">{s.name.replace(/Scenario [A-Z] — /, '')}</span>
                    <span className="block text-[10px] text-ink-500 font-normal">
                      {s.inputs.water_level_m}m · {s.inputs.inflow_ktcmd} kTCM/d
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-base-700/50 text-ink-200">
              {(data?.comparison_table ?? []).map((row, idx) => (
                <tr key={idx} className="hover:bg-base-700/30">
                  <td className="py-2.5 px-3 font-semibold text-ink-100">{row.metric}</td>
                  {scenarios.map((s) => (
                    <td key={s.scenario_id} className="py-2.5 px-3">
                      {row[s.scenario_id] ?? '—'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Chart + Map Comparison Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Comparative Chart */}
        <div className="panel p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-base-600/60 pb-3">
            <h3 className="font-display font-semibold text-sm text-ink-100">
              Risk Distribution &amp; Coverage Comparison
            </h3>
            <span className="font-mono text-[10px] text-signal-teal">ANALYTICS</span>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <XAxis dataKey="name" stroke="#8A96A8" fontSize={11} />
                <YAxis stroke="#8A96A8" fontSize={11} />
                <RechartsTooltip
                  contentStyle={{ backgroundColor: '#1C2634', borderColor: '#2E3D4E', borderRadius: 4, fontSize: 12 }}
                />
                <RechartsLegend wrapperStyle={{ fontSize: 11, paddingTop: 10 }} />
                <Bar dataKey="Critical" fill="#EF4444" name="Critical Zones" />
                <Bar dataKey="High" fill="#F97316" name="High Risk Zones" />
                <Bar dataKey="CoveragePct" fill="#2DD4BF" name="Sensor Coverage (%)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Selected Scenario Map Display */}
        <div className="panel p-3 relative flex flex-col justify-between">
          <div className="flex items-center justify-between px-2 py-1 mb-2">
            <div>
              <span className="data-label">Selected Scenario Map Overlay</span>
              <div className="font-display font-semibold text-sm text-ink-100">
                {viewingScenario?.name}
              </div>
            </div>
            <span className="font-mono text-xs text-signal-teal">
              {viewingScenario?.metrics?.critical_zones_count} Critical Zones
            </span>
          </div>

          <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="320px">
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name={layers.study_area?.river ? `${layers.study_area.river}` : 'River Centerline'} checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Scenario Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>
    </div>
  )
}
