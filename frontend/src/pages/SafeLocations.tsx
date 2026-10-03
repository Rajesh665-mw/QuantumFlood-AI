import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api } from '../services/api'
import type { SafeLocationEvaluationResponse, SafeLocation, RiskMap } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { SafeLocationMarkersLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

export default function SafeLocations() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<SafeLocationEvaluationResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)
  const [selectedLoc, setSelectedLoc] = useState<SafeLocation | null>(null)

  // Configurable weights
  const [weightElev, setWeightElev] = useState(0.25)
  const [weightRisk, setWeightRisk] = useState(0.35)
  const [weightDist, setWeightDist] = useState(0.20)
  const [weightAccess, setWeightAccess] = useState(0.20)
  const [minElev, setMinElev] = useState<number>(0)

  useEffect(() => {
    Promise.all([
      api.latestSafeLocations().catch(() => null),
      api.riskZones().catch(() => null),
    ])
      .then(([locs, rm]) => {
        if (locs) setData(locs)
        if (rm) setRiskMap(rm)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleEvaluate = async () => {
    setEvaluating(true)
    try {
      const res = await api.evaluateSafeLocations({
        weight_elevation: weightElev,
        weight_risk: weightRisk,
        weight_distance: weightDist,
        weight_accessibility: weightAccess,
        min_elevation_m: minElev > 0 ? minElev : undefined,
      })
      setData(res)
      if (res.locations.length > 0) {
        setSelectedLoc(res.locations[0])
      }
    } catch (err) {
      console.error('Failed to evaluate safe locations:', err)
    } finally {
      setEvaluating(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading lower-risk location finder…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const locations = data?.locations ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 1 · Risk-Aware Lower-Risk Location Finder</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Lower-Risk Assembly &amp; Safe Locations
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Multi-criteria decision analysis (MCDA) identifying public facilities, community campuses, and
          high-ground compounds with comparatively lower flood risk across the Vijayawada corridor.
        </p>
      </div>

      {/* Scientific Honesty Disclaimer Banner */}
      <div className="panel p-4 bg-base-900/80 border-signal-teal/30 flex items-start gap-3">
        <span className="w-2 h-2 rounded-full bg-signal-teal mt-1.5 shrink-0" />
        <div className="text-xs text-ink-300 leading-relaxed">
          <strong className="text-signal-teal">Model-Based Recommendation Notice:</strong> Recommendations
          are determined via open geospatial multi-criteria scoring combining modelled flood risk, SRTM
          topographic elevation, river distance, and arterial road class. Structural shelter inspection,
          live occupancy, and supplies are <span className="text-amber-400 font-mono">UNAVAILABLE / NOT SURVEYED</span>.
          This tool serves research decision-support, not an official government evacuation directive.
        </div>
      </div>

      {/* Control Configuration Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="panel p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-base-600/60 pb-3">
            <h2 className="font-display font-semibold text-sm text-ink-100">Scoring Weights</h2>
            <span className="font-mono text-[11px] text-signal-teal">MCDA MODEL</span>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Flood-Risk Weight</span>
                <span className="text-signal-teal">{Math.round(weightRisk * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightRisk}
                onChange={(e) => setWeightRisk(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Elevation Weight</span>
                <span className="text-signal-teal">{Math.round(weightElev * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightElev}
                onChange={(e) => setWeightElev(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">River Standoff Weight</span>
                <span className="text-signal-teal">{Math.round(weightDist * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightDist}
                onChange={(e) => setWeightDist(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Road Accessibility</span>
                <span className="text-signal-teal">{Math.round(weightAccess * 100)}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={weightAccess}
                onChange={(e) => setWeightAccess(parseFloat(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div className="pt-2 border-t border-base-600/60">
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-ink-300">Min. Elevation Filter</span>
                <span className="text-ink-100 font-bold">{minElev > 0 ? `${minElev} m` : 'Off'}</span>
              </div>
              <input
                type="range"
                min="0"
                max="35"
                step="5"
                value={minElev}
                onChange={(e) => setMinElev(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>
          </div>

          <button
            onClick={handleEvaluate}
            disabled={evaluating}
            className="w-full mt-2 py-2.5 px-4 rounded bg-signal-teal text-base-950 font-display font-semibold text-xs tracking-wide uppercase hover:bg-signal-tealDim transition-colors shadow-sm disabled:opacity-50"
          >
            {evaluating ? 'Evaluating Multi-Criteria…' : 'Re-Evaluate Locations'}
          </button>
        </div>

        {/* Map Container */}
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
              <LayersOverlay name="Candidate Safe Locations" checked>
                <SafeLocationMarkersLayer
                  locations={locations}
                  onLocationClick={(loc) => setSelectedLoc(loc)}
                />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>

      {/* Candidate Ranking Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display font-semibold text-lg text-ink-100">
            Ranked Recommendations ({locations.length} candidate sites)
          </h2>
          <span className="text-xs font-mono text-ink-500">SORTED BY MCDA SCORE DESCENDING</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {locations.map((loc, idx) => {
            const isSelected = selectedLoc?.id === loc.id
            const isTop = idx === 0
            return (
              <div
                key={loc.id}
                onClick={() => setSelectedLoc(loc)}
                className={`panel p-4 cursor-pointer transition-all duration-150 relative ${
                  isSelected
                    ? 'border-signal-teal ring-1 ring-signal-teal/50 bg-base-800/90'
                    : 'hover:border-base-500 hover:bg-base-850'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-mono text-[10px] text-signal-teal uppercase tracking-wider">
                      #{idx + 1} · {loc.category.replace(/_/g, ' ')}
                    </span>
                    <h3 className="font-display font-semibold text-sm text-ink-100 mt-0.5">
                      {loc.name}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-lg font-bold text-signal-teal">
                      {loc.recommendation_score}
                    </span>
                    <span className="text-[10px] font-mono text-ink-500 block">/ 100</span>
                  </div>
                </div>

                {isTop && (
                  <span className="inline-block mt-2 px-2 py-0.5 bg-emerald-500/20 text-emerald-300 font-mono text-[10px] rounded border border-emerald-500/40">
                    Highest Recommended Site
                  </span>
                )}

                <div className="grid grid-cols-2 gap-2 mt-3 pt-3 border-t border-base-600/50 text-xs font-mono">
                  <div>
                    <span className="text-ink-500 text-[10px] block uppercase">Elevation</span>
                    <span className="text-ink-100 font-medium">{loc.elevation_m} m</span>
                  </div>
                  <div>
                    <span className="text-ink-500 text-[10px] block uppercase">River Distance</span>
                    <span className="text-ink-100 font-medium">{loc.distance_to_river_km} km</span>
                  </div>
                  <div>
                    <span className="text-ink-500 text-[10px] block uppercase">Modelled Risk</span>
                    <span
                      className={`font-semibold ${
                        loc.modelled_risk_level === 'LOW'
                          ? 'text-emerald-400'
                          : loc.modelled_risk_level === 'MODERATE'
                          ? 'text-amber-400'
                          : 'text-red-400'
                      }`}
                    >
                      {loc.modelled_risk_level} ({loc.assigned_zone_id})
                    </span>
                  </div>
                  <div>
                    <span className="text-ink-500 text-[10px] block uppercase">Road Access</span>
                    <span className="text-ink-200 truncate block">{loc.primary_road_access}</span>
                  </div>
                </div>

                <p className="mt-3 text-xs text-ink-400 leading-relaxed italic bg-base-900/50 p-2.5 rounded border border-base-700/60">
                  "{loc.explanation}"
                </p>

                <div className="mt-3 flex items-center justify-between text-[11px] font-mono text-ink-500">
                  <span>Capacity: <strong className="text-amber-400">{loc.capacity_status}</strong></span>
                  <span className="text-signal-teal text-[10px]">Click to inspect</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
