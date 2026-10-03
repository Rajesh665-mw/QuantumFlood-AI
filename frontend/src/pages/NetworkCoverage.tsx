import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { CircleMarker, Polyline, Popup } from 'react-leaflet'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError } from '../services/api'
import type { OptimizationRunResponse, RiskMap as RiskMapType } from '../types'
import { LoadingState, ErrorState, EmptyState } from '../components/LoadingState'
import StatCard from '../components/StatCard'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { useMapLayers } from '../hooks/useMapLayers'

export default function NetworkCoverage() {
  const { layers, loading: layersLoading, error: layersError } = useMapLayers()
  const [result, setResult] = useState<OptimizationRunResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMapType | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.optimizationResults(), api.coverageAnalysis(), api.riskZones().catch(() => null)])
      .then(([opt, coverage, risk]) => {
        setResult({
          optimization: opt.optimization,
          connectivity: opt.connectivity,
          coverage_summary: coverage,
          candidates_generated: 0,
          params: opt.params,
        })
        setRiskMap(risk)
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'No optimisation results available yet.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading || layersLoading) return <LoadingState label="Loading network topology…" />
  if (layersError || !layers) return <ErrorState message={layersError ?? 'Map layers unavailable.'} />

  if (error || !result) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader />
        <EmptyState
          title="No coverage data yet"
          description="Run sensor optimisation first from the Sensor Optimisation page — this page reports on its actual output."
        />
      </div>
    )
  }

  const cov = result.coverage_summary
  const chartData = [
    { name: 'Connected', value: cov.connected_sensors, color: '#4E9A6B' },
    { name: 'Disconnected', value: cov.disconnected_sensors, color: '#D2504A' },
  ]

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const sensorLookup = new Map(result.optimization.selected_sensors.map((s) => [s.candidate_id, s]))
  const nodeLookup = new Map(result.connectivity.comm_nodes.map((n) => [n.comm_node_id, n]))
  const disconnectedIds = new Set(result.connectivity.disconnected_sensor_ids)
  const criticalUncovered = result.optimization.uncovered_priority_zone_ids.filter(
    (zid) => zoneRiskLookup.get(zid)?.risk_level === 'CRITICAL',
  )

  return (
    <div className="flex flex-col gap-8">
      <PageHeader />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="High-Risk Coverage" value={`${cov.high_risk_zone_covered}/${cov.high_risk_zone_total}`} />
        <StatCard label="Critical Coverage" value={`${cov.critical_zone_covered}/${cov.critical_zone_total}`} accent="critical" />
        <StatCard label="Sensors Deployed" value={`${cov.sensors_deployed}/${cov.sensor_budget}`} />
        <StatCard label="Comm Nodes" value={`${cov.comm_nodes_deployed}/${cov.comm_node_budget}`} sublabel={cov.comm_node_budget_exhausted ? 'Budget exhausted' : 'Within budget'} />
        <StatCard label="Connected Sensors" value={cov.connected_sensors} accent="low" />
        <StatCard label="Disconnected Sensors" value={cov.disconnected_sensors} accent={cov.disconnected_sensors > 0 ? 'critical' : 'low'} />
        <StatCard label="Total Coverage" value={cov.total_coverage_percentage} unit="%" accent="teal" />
        <StatCard label="Connectivity" value={cov.connectivity_percentage} unit="%" accent="teal" />
      </div>

      <div className="panel p-2 md:p-4">
        <span className="data-label px-3 pt-2 block">Geographic Network Topology</span>
        <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
          <LayersControl position="topright">
            <LayersOverlay name="Study Area Boundary" checked>
              <StudyAreaBoundaryLayer boundary={layers.boundary} />
            </LayersOverlay>
            <LayersOverlay name="Krishna River" checked>
              <RiverLayer river={layers.river} />
            </LayersOverlay>
            <LayersOverlay name="Flood Risk Zones" checked={false}>
              <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
            </LayersOverlay>
            <LayersOverlay name="Connections (sensor ↔ comm node)" checked>
              <>
                {result.connectivity.connections.map((c, i) => {
                  const sensor = sensorLookup.get(c.sensor_id)
                  const node = nodeLookup.get(c.comm_node_id)
                  if (!sensor || !node) return null
                  return (
                    <Polyline
                      key={i}
                      positions={[[sensor.lat, sensor.lon], [node.lat, node.lon]]}
                      pathOptions={{ color: '#4E9A6B', weight: 2, opacity: 0.7 }}
                    />
                  )
                })}
              </>
            </LayersOverlay>
            <LayersOverlay name="Sensors" checked>
              <>
                {result.optimization.selected_sensors.map((s) => {
                  const disconnected = disconnectedIds.has(s.candidate_id)
                  return (
                    <CircleMarker
                      key={s.candidate_id}
                      center={[s.lat, s.lon]}
                      radius={disconnected ? 8 : 6}
                      pathOptions={{
                        color: disconnected ? '#D2504A' : '#2DD4BF',
                        fillColor: disconnected ? '#D2504A' : '#2DD4BF',
                        fillOpacity: disconnected ? 0.3 : 1,
                        weight: disconnected ? 3 : 2,
                        dashArray: disconnected ? '3 3' : undefined,
                      }}
                    >
                      <Popup>
                        <div className="font-mono text-xs leading-relaxed">
                          <div className="font-semibold">{s.candidate_id}</div>
                          <div>Zone: {s.zone_id}</div>
                          <div>Status: {disconnected ? 'DISCONNECTED — outside comm range/budget' : 'Connected'}</div>
                        </div>
                      </Popup>
                    </CircleMarker>
                  )
                })}
              </>
            </LayersOverlay>
            <LayersOverlay name="Communication Nodes" checked>
              <>
                {result.connectivity.comm_nodes.map((n) => (
                  <CircleMarker key={n.comm_node_id} center={[n.lat, n.lon]} radius={11} pathOptions={{ color: '#C99A3B', fillOpacity: 0, weight: 2 }}>
                    <Popup>
                      <div className="font-mono text-xs leading-relaxed">
                        <div className="font-semibold">{n.comm_node_id}</div>
                        <div>Connected sensors: {n.connects_sensor_ids.length}</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </>
            </LayersOverlay>
            <LayersOverlay name="Critical Uncovered Zones" checked>
              <>
                {layers.zones
                  .filter((z) => criticalUncovered.includes(z.zone_id))
                  .map((z) => (
                    <CircleMarker
                      key={z.zone_id}
                      center={[z.centroid.lat, z.centroid.lon]}
                      radius={14}
                      pathOptions={{ color: '#D2504A', fillOpacity: 0, weight: 3, dashArray: '2 4' }}
                    >
                      <Popup>
                        <div className="font-mono text-xs">
                          <div className="font-semibold">{z.zone_id}</div>
                          <div>CRITICAL — uncovered by any sensor</div>
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}
              </>
            </LayersOverlay>
          </LayersControl>
        </GeoMap>
      </div>

      <div className="panel p-4 flex flex-wrap items-center gap-4 text-xs text-ink-500">
        <LegendItem color="#4E9A6B" label="Active connection" line />
        <LegendItem color="#2DD4BF" label="Connected sensor" />
        <LegendItem color="#D2504A" label="Disconnected sensor" dashed />
        <LegendItem color="#C99A3B" label="Communication node" outline />
        <LegendItem color="#D2504A" label="Critical uncovered zone" outline dashed />
      </div>

      <div className="panel p-5">
        <span className="data-label">Sensor Connectivity Breakdown</span>
        <div className="h-56 mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical">
              <CartesianGrid stroke="#29343F" strokeDasharray="2 4" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#8A96A8' }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#8A96A8' }} width={90} />
              <Tooltip contentStyle={{ background: '#1C2634', border: '1px solid #29343F', fontSize: 12 }} />
              <Bar dataKey="value" radius={[0, 3, 3, 0]}>
                {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="panel p-5">
          <span className="data-label">Communication Nodes</span>
          <div className="flex flex-col gap-2 mt-3 max-h-64 overflow-y-auto">
            {result.connectivity.comm_nodes.map((n) => (
              <div key={n.comm_node_id} className="flex justify-between items-center bg-base-700 rounded px-3 py-2 text-sm">
                <span className="font-mono text-ink-100">{n.comm_node_id}</span>
                <span className="text-ink-500 text-xs">{n.connects_sensor_ids.length} sensor(s)</span>
              </div>
            ))}
          </div>
        </div>
        <div className="panel p-5">
          <span className="data-label">Coverage Gaps</span>
          {cov.uncovered_priority_zone_ids.length === 0 ? (
            <p className="text-risk-low text-sm mt-3">No uncovered priority zones — full coverage achieved.</p>
          ) : (
            <div className="flex flex-wrap gap-2 mt-3">
              {cov.uncovered_priority_zone_ids.map((zid) => (
                <span
                  key={zid}
                  className={`font-mono text-xs px-2 py-1 rounded ${
                    criticalUncovered.includes(zid) ? 'bg-risk-criticalBg text-risk-critical border border-risk-critical/40' : 'bg-base-700 text-risk-high'
                  }`}
                >
                  {zid}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function PageHeader() {
  return (
    <div>
      <span className="eyebrow">Modules 7–8 · Network & Coverage Analysis</span>
      <h1 className="font-display text-2xl text-ink-100 mt-1">Network &amp; Coverage Analysis</h1>
      <p className="text-ink-500 text-sm mt-2 max-w-2xl">
        Communication-node connectivity computed from real great-circle distances between deployed
        sensors and relay sites, under a limited communication-node budget. Connection lines on the map
        reflect the actual backend connectivity result — nothing here is a visual approximation.
      </p>
    </div>
  )
}

function LegendItem({ color, label, line, outline, dashed }: { color: string; label: string; line?: boolean; outline?: boolean; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      {line ? (
        <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: color }} />
      ) : (
        <span
          className="w-3 h-3 rounded-full inline-block"
          style={outline ? { border: `2px ${dashed ? 'dashed' : 'solid'} ${color}` } : { backgroundColor: color }}
        />
      )}
      <span>{label}</span>
    </div>
  )
}
