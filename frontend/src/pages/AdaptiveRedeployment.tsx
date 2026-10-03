import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api } from '../services/api'
import type { AdaptiveRedeploymentResponse, RiskMap } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { SensorRedeploymentLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

export default function AdaptiveRedeployment() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<AdaptiveRedeploymentResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [optimizing, setOptimizing] = useState(false)

  const [sensorBudget, setSensorBudget] = useState(8)
  const [coverageRadius, setCoverageRadius] = useState(2.5)

  useEffect(() => {
    Promise.all([
      api.latestRedeployment().catch(() => null),
      api.riskZones().catch(() => null),
    ])
      .then(([redeploy, rm]) => {
        if (redeploy) setData(redeploy)
        if (rm) setRiskMap(rm)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleRunRedeploy = async () => {
    setOptimizing(true)
    try {
      const res = await api.redeploySensors({
        sensor_budget: sensorBudget,
        coverage_radius_km: coverageRadius,
        use_active_sensors: true,
      })
      setData(res)
    } catch (err) {
      console.error('Failed to run adaptive redeployment:', err)
    } finally {
      setOptimizing(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading adaptive sensor redeployment…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const actions = data?.actions ?? []
  const summary = data?.summary

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 3 · Dynamic Sensor Reconfiguration</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Adaptive Sensor Redeployment
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Solves transition optimization to determine which existing deployed flood sensors should remain,
          relocate, or be supplemented when the flood risk distribution shifts across the corridor.
        </p>
      </div>

      {/* Control Grid + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="panel p-5 space-y-4">
          <h2 className="font-display font-semibold text-sm text-ink-100 border-b border-base-600/60 pb-3">
            Redeployment Budget
          </h2>

          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Sensor Budget</span>
                <span className="text-signal-teal font-bold">{sensorBudget} stations</span>
              </div>
              <input
                type="range"
                min="4"
                max="16"
                step="1"
                value={sensorBudget}
                onChange={(e) => setSensorBudget(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Sensor Radius (R)</span>
                <span className="text-signal-teal font-bold">{coverageRadius.toFixed(1)} km</span>
              </div>
              <input
                type="range"
                min="1.5"
                max="5.0"
                step="0.5"
                value={coverageRadius}
                onChange={(e) => setCoverageRadius(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>
          </div>

          <button
            onClick={handleRunRedeploy}
            disabled={optimizing}
            className="w-full mt-3 py-2.5 px-4 rounded bg-signal-teal text-base-950 font-display font-semibold text-xs tracking-wide uppercase hover:bg-signal-tealDim transition-colors shadow-sm disabled:opacity-50"
          >
            {optimizing ? 'Optimising Transitions…' : 'Optimise Redeployment'}
          </button>
        </div>

        {/* Map */}
        <div className="lg:col-span-3 panel p-2 md:p-3 relative">
          <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name="Krishna River" checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Modelled Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
              <LayersOverlay name="Sensor Movement Vectors" checked>
                <SensorRedeploymentLayer actions={actions} />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>

      {/* Metrics Summary */}
      {summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="panel p-4 border-l-2 border-emerald-400">
              <span className="data-label block">Sensors Kept</span>
              <span className="font-mono text-2xl font-bold text-ink-100 mt-1 block">
                {summary.sensors_kept}
              </span>
              <span className="text-[11px] font-mono text-ink-500">Remain at optimal site</span>
            </div>

            <div className="panel p-4 border-l-2 border-signal-teal">
              <span className="data-label block">Sensors Relocated</span>
              <span className="font-mono text-2xl font-bold text-signal-teal mt-1 block">
                {summary.sensors_relocated}
              </span>
              <span className="text-[11px] font-mono text-ink-500">Moved to cover risk surge</span>
            </div>

            <div className="panel p-4 border-l-2 border-blue-400">
              <span className="data-label block">Sensors Added</span>
              <span className="font-mono text-2xl font-bold text-blue-400 mt-1 block">
                {summary.sensors_added}
              </span>
              <span className="text-[11px] font-mono text-ink-500">Budget expansion units</span>
            </div>

            <div className="panel p-4 border-l-2 border-purple-400">
              <span className="data-label block">Critical Zone Coverage</span>
              <span className="font-mono text-2xl font-bold text-purple-400 mt-1 block">
                {summary.updated_coverage.critical_coverage_percentage}%
              </span>
              <span className="text-[11px] font-mono text-emerald-400">
                +{summary.improvements.critical_coverage_percentage_gain}% improvement
              </span>
            </div>
          </div>

          {/* Narrative */}
          <div className="panel p-4 bg-base-900/60 border-base-700">
            <span className="eyebrow block">Algorithm Decision Summary</span>
            <p className="mt-2 text-sm text-ink-200 font-mono leading-relaxed">
              {data?.recommendation_narrative}
            </p>
          </div>

          {/* Per-Sensor Action Plan Table */}
          <div className="panel p-5 space-y-3">
            <h3 className="font-display font-semibold text-sm text-ink-100">
              Sensor-by-Sensor Transition Action Plan
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-ink-500 border-b border-base-600 text-left">
                    <th className="py-2.5 px-3">Action</th>
                    <th className="py-2.5 px-3">Sensor Site</th>
                    <th className="py-2.5 px-3">Current Location</th>
                    <th className="py-2.5 px-3">Target Location</th>
                    <th className="py-2.5 px-3">Move Distance</th>
                    <th className="py-2.5 px-3">Optimization Justification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-base-700/50 text-ink-200">
                  {actions.map((act, i) => (
                    <tr key={i} className="hover:bg-base-700/30">
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            act.action === 'KEEP'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                              : act.action === 'RELOCATE'
                              ? 'bg-teal-500/20 text-signal-teal border border-teal-500/40'
                              : act.action === 'ADD'
                              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                              : 'bg-red-500/20 text-red-300 border border-red-500/40'
                          }`}
                        >
                          {act.action}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-ink-100">{act.sensor_id}</td>
                      <td className="py-2.5 px-3 text-ink-400">
                        {act.current_site ? `${act.current_site.candidate_id} (${act.current_site.zone_id})` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-ink-100">
                        {act.target_site ? `${act.target_site.candidate_id} (${act.target_site.zone_id})` : '—'}
                      </td>
                      <td className="py-2.5 px-3">
                        {act.distance_km > 0 ? `${act.distance_km} km` : '0 km'}
                      </td>
                      <td className="py-2.5 px-3 text-ink-300 max-w-md">{act.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
