import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api } from '../services/api'
import type { NetworkResilienceResponse, RiskMap } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { NetworkResilienceLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

export default function NetworkResilience() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<NetworkResilienceResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [simulating, setSimulating] = useState(false)

  const [selectedFailedNodes, setSelectedFailedNodes] = useState<string[]>([])
  const [commRange, setCommRange] = useState(4.0)

  useEffect(() => {
    Promise.all([
      api.latestNetworkResilience().catch(() => null),
      api.riskZones().catch(() => null),
    ])
      .then(([resil, rm]) => {
        if (resil) {
          setData(resil)
          setSelectedFailedNodes(resil.simulation_parameters?.failed_node_ids ?? [])
        }
        if (rm) setRiskMap(rm)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleToggleNodeFailure = (nodeId: string) => {
    setSelectedFailedNodes((prev) =>
      prev.includes(nodeId) ? prev.filter((id) => id !== nodeId) : [...prev, nodeId]
    )
  }

  const handleSimulate = async () => {
    setSimulating(true)
    try {
      const res = await api.simulateNetworkResilience({
        failed_node_ids: selectedFailedNodes,
        comm_range_km: commRange,
      })
      setData(res)
    } catch (err) {
      console.error('Failed to simulate network resilience:', err)
    } finally {
      setSimulating(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading network resilience simulator…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const metrics = data?.metrics
  const netState = data?.network_state
  const recoveryPlan = data?.recovery_plan

  // All comm nodes available for toggling
  const allNodes = [
    ...(netState?.surviving_nodes ?? []),
    ...(netState?.failed_nodes ?? []),
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 4 · Network Fault Tolerance &amp; Recovery</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Communication Failure &amp; Network Resilience
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Simulate node outages across the sensor telemetry network, measure resulting connectivity and
          coverage degradation, and algorithmically identify optimal recovery interventions.
        </p>
      </div>

      {/* Control Grid + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="panel p-5 space-y-4">
          <h2 className="font-display font-semibold text-sm text-ink-100 border-b border-base-600/60 pb-3">
            Node Outage Simulation
          </h2>

          <div className="space-y-3">
            <label className="data-label block">Select Node(s) to Fail:</label>
            <div className="space-y-2 max-h-48 overflow-y-auto p-1 font-mono text-xs">
              {allNodes.length === 0 && (
                <div className="text-ink-500 text-xs italic">
                  Run sensor optimisation first to deploy initial communication nodes.
                </div>
              )}
              {allNodes.map((n) => {
                const isFailed = selectedFailedNodes.includes(n.comm_node_id)
                return (
                  <label
                    key={n.comm_node_id}
                    className={`flex items-center justify-between p-2.5 rounded cursor-pointer border transition-colors ${
                      isFailed
                        ? 'bg-red-950/40 border-red-500/60 text-red-200'
                        : 'bg-base-900 border-base-700 text-ink-300 hover:border-base-500'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isFailed}
                        onChange={() => handleToggleNodeFailure(n.comm_node_id)}
                        className="accent-red-500"
                      />
                      <span className="font-bold">{n.comm_node_id}</span>
                    </div>
                    <span className="text-[10px] text-ink-500">
                      Co-located: {n.co_located_with}
                    </span>
                  </label>
                )
              })}
            </div>

            <div className="pt-2 border-t border-base-600/60">
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Comm Range (Km)</span>
                <span className="text-signal-teal font-bold">{commRange} km</span>
              </div>
              <input
                type="range"
                min="2.0"
                max="8.0"
                step="0.5"
                value={commRange}
                onChange={(e) => setCommRange(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>
          </div>

          <button
            onClick={handleSimulate}
            disabled={simulating}
            className="w-full mt-3 py-2.5 px-4 rounded bg-signal-teal text-base-950 font-display font-semibold text-xs tracking-wide uppercase hover:bg-signal-tealDim transition-colors shadow-sm disabled:opacity-50"
          >
            {simulating ? 'Simulating Fault & Recovery…' : 'Simulate Failure & Recover'}
          </button>
        </div>

        {/* Map */}
        <div className="lg:col-span-3 panel p-2 md:p-3 relative">
          <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name={layers.study_area?.river ? `${layers.study_area.river}` : 'River Centerline'} checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Modelled Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
              <LayersOverlay name="Network Resilience State" checked>
                <NetworkResilienceLayer
                  survivingNodes={netState?.surviving_nodes ?? []}
                  failedNodes={netState?.failed_nodes ?? []}
                  activeConnections={netState?.active_connections ?? []}
                  severedConnections={netState?.severed_connections ?? []}
                  recoveryNode={recoveryPlan?.recommended_site}
                />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>

      {/* Metrics Row */}
      {metrics && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="panel p-4 border-l-2 border-emerald-400">
              <span className="data-label block">Baseline Connectivity</span>
              <span className="font-mono text-2xl font-bold text-ink-100 mt-1 block">
                {metrics.baseline_connectivity_pct}%
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                {metrics.baseline_connected} / {metrics.total_sensors} sensors connected
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-red-500">
              <span className="data-label block">Post-Failure Connectivity</span>
              <span className="font-mono text-2xl font-bold text-red-400 mt-1 block">
                {metrics.post_failure_connectivity_pct}%
              </span>
              <span className="text-[11px] font-mono text-red-300">
                -{metrics.connectivity_loss_pct}% loss · {metrics.post_failure_disconnected} isolated
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-amber-400">
              <span className="data-label block">Critical Sensors Lost</span>
              <span className="font-mono text-2xl font-bold text-amber-400 mt-1 block">
                {metrics.affected_critical_sensors.length}
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                Sensors in CRITICAL zones disconnected
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-signal-teal">
              <span className="data-label block">Post-Recovery Restored</span>
              <span className="font-mono text-2xl font-bold text-signal-teal mt-1 block">
                {recoveryPlan?.post_recovery_connectivity_pct}%
              </span>
              <span className="text-[11px] font-mono text-emerald-300">
                +{recoveryPlan?.reconnected_count} sensors reconnected
              </span>
            </div>
          </div>

          {/* Recovery Recommendation Card */}
          {recoveryPlan && (
            <div className="panel p-5 border-l-4 border-signal-teal bg-base-900/60 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-signal-teal uppercase tracking-wider">
                  Algorithmic Recovery Plan
                </span>
                <span className="px-2 py-0.5 bg-signal-teal/20 text-signal-teal text-[10px] font-mono rounded">
                  {recoveryPlan.action_type.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-sm text-ink-200 font-mono leading-relaxed mt-2">
                "{recoveryPlan.explanation}"
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
