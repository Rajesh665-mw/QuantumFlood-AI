import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api } from '../services/api'
import type {
  EvacuationRouteResponse,
  SafeLocationEvaluationResponse,
  RiskMap,
} from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { EvacuationRouteLayer, SafeLocationMarkersLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

export default function EvacuationRouting() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [routeData, setRouteData] = useState<EvacuationRouteResponse | null>(null)
  const [safeLocations, setSafeLocations] = useState<SafeLocationEvaluationResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [routing, setRouting] = useState(false)

  // Origins: key landmark coordinates in high-exposure corridor areas
  const ORIGIN_OPTIONS = [
    { id: 'prakasam_barrage', name: 'Prakasam Barrage West', lat: 16.5061, lon: 80.6050, note: 'Near Riverfront / Gauge' },
    { id: 'kanakadurga', name: 'Kanakadurga Flyover Approach', lat: 16.5128, lon: 80.6039, note: 'West Urban Gateway' },
    { id: 'governorpet', name: 'Governorpet Central / MG Road', lat: 16.5100, lon: 80.6250, note: 'Dense Lowland Urban Center' },
    { id: 'gollapudi', name: 'Gollapudi Bypass Corridor', lat: 16.5350, lon: 80.5750, note: 'Northwest Inflow Gateway' },
    { id: 'varadhi_north', name: 'Kanaka Durga Varadhi North', lat: 16.4950, lon: 80.6180, note: 'Bridgehead Embankment' },
  ]

  const [selectedOriginId, setSelectedOriginId] = useState(ORIGIN_OPTIONS[0].id)
  const [selectedDestId, setSelectedDestId] = useState<string>('')
  const [riskPenaltyBeta, setRiskPenaltyBeta] = useState(3.0)

  useEffect(() => {
    Promise.all([
      api.latestSafeLocations().catch(() => null),
      api.riskZones().catch(() => null),
      api.latestEvacuationRoute().catch(() => null),
    ])
      .then(([locs, rm, latestRoute]) => {
        if (locs) {
          setSafeLocations(locs)
          if (locs.locations.length > 0) {
            setSelectedDestId(locs.locations[0].id)
          }
        }
        if (rm) setRiskMap(rm)
        if (latestRoute) setRouteData(latestRoute)
      })
      .finally(() => setLoading(false))
  }, [])

  const handlePlanRoute = async () => {
    const origin = ORIGIN_OPTIONS.find((o) => o.id === selectedOriginId)
    const dest = safeLocations?.locations.find((l) => l.id === selectedDestId)

    if (!origin || !dest) return

    setRouting(true)
    try {
      const res = await api.planEvacuationRoute({
        origin_lat: origin.lat,
        origin_lon: origin.lon,
        dest_lat: dest.lat,
        dest_lon: dest.lon,
        origin_name: origin.name,
        dest_name: dest.name,
        risk_penalty_beta: riskPenaltyBeta,
      })
      setRouteData(res)
    } catch (err) {
      console.error('Failed to plan evacuation route:', err)
    } finally {
      setRouting(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading evacuation routing system…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const primary = routeData?.primary_route
  const alternative = routeData?.alternative_route

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 2 · Dynamic Evacuation Routing</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Model-Based Evacuation Route Planner
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Risk-penalised graph routing algorithm across Vijayawada's arterial network, steering transit away
          from inundated riverfront corridors toward validated lower-risk assembly facilities.
        </p>
      </div>

      {/* Honesty Banner */}
      <div className="panel p-4 bg-base-900/80 border-signal-teal/30 flex items-start gap-3">
        <span className="w-2 h-2 rounded-full bg-signal-teal mt-1.5 shrink-0" />
        <div className="text-xs text-ink-300 leading-relaxed">
          <strong className="text-signal-teal">Modelled Route Navigation Disclaimer:</strong> All routes and
          segment safety ratings are computed based on modelled spatial flood risk. Live physical road closures,
          bridge inundations, debris, and traffic bottlenecks are not available without physical road telemetry.
          Always follow real-time on-ground civic administration and police instructions during an emergency.
        </div>
      </div>

      {/* Control Panel + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="panel p-5 space-y-4">
          <h2 className="font-display font-semibold text-sm text-ink-100 border-b border-base-600/60 pb-3">
            Evacuation Parameters
          </h2>

          <div className="space-y-3">
            <div>
              <label className="data-label block mb-1.5">Origin (High-Exposure Area)</label>
              <select
                value={selectedOriginId}
                onChange={(e) => setSelectedOriginId(e.target.value)}
                className="w-full bg-base-900 border border-base-600 text-ink-100 text-xs rounded p-2.5 font-mono focus:border-signal-teal outline-none"
              >
                {ORIGIN_OPTIONS.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name} ({o.note})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="data-label block mb-1.5">Destination (Recommended Facility)</label>
              <select
                value={selectedDestId}
                onChange={(e) => setSelectedDestId(e.target.value)}
                className="w-full bg-base-900 border border-base-600 text-ink-100 text-xs rounded p-2.5 font-mono focus:border-signal-teal outline-none"
              >
                {(safeLocations?.locations ?? []).map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({l.recommendation_score} pts · {l.elevation_m}m)
                  </option>
                ))}
              </select>
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Flood-Risk Aversion (β)</span>
                <span className="text-signal-teal">{riskPenaltyBeta.toFixed(1)}x</span>
              </div>
              <input
                type="range"
                min="0"
                max="8"
                step="0.5"
                value={riskPenaltyBeta}
                onChange={(e) => setRiskPenaltyBeta(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
              <span className="text-[10px] font-mono text-ink-500 block mt-1">
                Higher values penalise routes passing through HIGH / CRITICAL zones more heavily.
              </span>
            </div>
          </div>

          <button
            onClick={handlePlanRoute}
            disabled={routing}
            className="w-full mt-3 py-2.5 px-4 rounded bg-signal-teal text-base-950 font-display font-semibold text-xs tracking-wide uppercase hover:bg-signal-tealDim transition-colors shadow-sm disabled:opacity-50"
          >
            {routing ? 'Computing Optimal Route…' : 'Plan Evacuation Route'}
          </button>
        </div>

        {/* Map Display */}
        <div className="lg:col-span-3 panel p-2 md:p-3 relative">
          <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name="Krishna River" checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
              <LayersOverlay name="Evacuation Routes" checked>
                <EvacuationRouteLayer
                  primaryRoute={primary}
                  alternativeRoute={alternative}
                  origin={routeData?.origin}
                  destination={routeData?.destination}
                />
              </LayersOverlay>
              <LayersOverlay name="Safe Locations" checked>
                <SafeLocationMarkersLayer locations={safeLocations?.locations ?? []} />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>

      {/* Route Details & Comparison */}
      {routeData && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Primary Route Card */}
            <div className="panel p-5 border-l-4 border-signal-teal bg-base-900/60">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-signal-teal uppercase tracking-wider">
                  Primary Route (Risk-Averse)
                </span>
                <span className="px-2 py-0.5 bg-signal-teal/20 text-signal-teal text-[10px] font-mono rounded">
                  RECOMMENDED
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 mt-4 text-xs font-mono">
                <div>
                  <span className="text-ink-500 text-[10px] block">TOTAL DISTANCE</span>
                  <span className="text-ink-100 text-lg font-bold">{primary?.total_distance_km} km</span>
                </div>
                <div>
                  <span className="text-ink-500 text-[10px] block">EST. ROUTE RISK</span>
                  <span className="text-emerald-400 text-lg font-bold">
                    {primary?.estimated_route_risk_score} / 4.0
                  </span>
                </div>
                <div>
                  <span className="text-ink-500 text-[10px] block">HIGH-RISK LEGS</span>
                  <span className="text-ink-100 text-lg font-bold">{primary?.high_risk_segments_count}</span>
                </div>
              </div>
              <p className="mt-4 text-xs text-ink-300 leading-relaxed italic bg-base-950/50 p-3 rounded border border-base-700/60">
                "{routeData.explanation}"
              </p>
            </div>

            {/* Alternative Shortest Route Card */}
            <div className="panel p-5 border-l-4 border-amber-500 bg-base-900/60">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-amber-400 uppercase tracking-wider">
                  Alternative Route (Shortest Physical)
                </span>
                <span className="px-2 py-0.5 bg-amber-500/20 text-amber-300 text-[10px] font-mono rounded">
                  SHORTEST
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3 mt-4 text-xs font-mono">
                <div>
                  <span className="text-ink-500 text-[10px] block">TOTAL DISTANCE</span>
                  <span className="text-ink-100 text-lg font-bold">{alternative?.total_distance_km} km</span>
                </div>
                <div>
                  <span className="text-ink-500 text-[10px] block">EST. ROUTE RISK</span>
                  <span className="text-amber-400 text-lg font-bold">
                    {alternative?.estimated_route_risk_score} / 4.0
                  </span>
                </div>
                <div>
                  <span className="text-ink-500 text-[10px] block">HIGH-RISK LEGS</span>
                  <span className="text-red-400 text-lg font-bold">{alternative?.high_risk_segments_count}</span>
                </div>
              </div>
              <p className="mt-4 text-xs text-ink-400 leading-relaxed italic bg-base-950/50 p-3 rounded border border-base-700/60">
                Takes direct corridors regardless of flood exposure, resulting in higher accumulated risk along
                riverfront segments.
              </p>
            </div>
          </div>

          {/* Segment Breakdown Table */}
          {primary && primary.segments.length > 0 && (
            <div className="panel p-5 space-y-3">
              <h3 className="font-display font-semibold text-sm text-ink-100">
                Primary Route Segment Breakdown
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-ink-500 border-b border-base-600 text-left">
                      <th className="py-2 px-3">Segment Road</th>
                      <th className="py-2 px-3">Road Class</th>
                      <th className="py-2 px-3">Distance</th>
                      <th className="py-2 px-3">Modelled Risk</th>
                      <th className="py-2 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-base-700/50 text-ink-200">
                    {primary.segments.map((seg) => (
                      <tr key={seg.edge_id} className="hover:bg-base-700/30">
                        <td className="py-2 px-3 font-medium text-ink-100">{seg.road_name}</td>
                        <td className="py-2 px-3 text-ink-400">{seg.road_class.replace(/_/g, ' ')}</td>
                        <td className="py-2 px-3">{seg.distance_km} km</td>
                        <td className="py-2 px-3">
                          <span
                            className={`font-semibold ${
                              seg.risk_level === 'LOW'
                                ? 'text-emerald-400'
                                : seg.risk_level === 'MODERATE'
                                ? 'text-amber-400'
                                : 'text-red-400'
                            }`}
                          >
                            {seg.risk_level} (Score {seg.modelled_risk_score})
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          {seg.is_high_risk ? (
                            <span className="text-red-400 font-semibold">⚠ High Exposure Warning</span>
                          ) : (
                            <span className="text-emerald-400">Passable</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
