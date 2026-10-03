import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError } from '../services/api'
import type { RiskMap as RiskMapType } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import RiskBadge from '../components/RiskBadge'
import RiskLegend from '../components/map/RiskLegend'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { useMapLayers } from '../hooks/useMapLayers'

export default function RiskMap() {
  const { layers, loading, error: layersError } = useMapLayers()
  const [riskMap, setRiskMap] = useState<RiskMapType | null>(null)
  const [riskLoading, setRiskLoading] = useState(true)

  useEffect(() => {
    api.riskZones().then(setRiskMap).catch(() => setRiskMap(null)).finally(() => setRiskLoading(false))
  }, [])

  if (loading) return <LoadingState label="Loading geospatial layers…" />
  if (layersError || !layers) return <ErrorState message={layersError ?? 'Map layers unavailable.'} />

  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">Module 4 · Geospatial Risk Mapping</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Flood Risk Map</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          {layers.study_area.scope_note ?? layers.study_area.name}
        </p>
        <p className="text-ink-700 text-xs mt-2 max-w-2xl">
          Geometry mode: <span className="font-mono text-signal-teal">{layers.geometry_mode}</span> — river
          geometry loaded from a local project-managed dataset; risk zones use a documented grid spatial
          model (see Data &amp; Analytics for source/resolution notes).
        </p>
      </div>

      {!riskLoading && !riskMap && (
        <div className="panel p-4 text-sm text-ink-300 border-signal-tealDim/40">
          No risk classification generated yet. Zones are shown with geometry only. Run a forecast and
          risk generation from the Flood Forecasting page to see colour-coded risk levels.
        </div>
      )}

      <div className="panel p-2 md:p-4">
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
          </LayersControl>
        </GeoMap>
      </div>

      <RiskLegend riverName={layers.study_area.river} />

      {riskMap && (
        <div className="panel p-5">
          <span className="data-label">Base Forecast Classification</span>
          <div className="flex items-center gap-3 mt-2">
            <RiskBadge level={riskMap.base_classification.overall_risk} />
            <span className="text-ink-500 text-sm">{riskMap.base_classification.explanation}</span>
          </div>
          {riskMap.proximity_rule && (
            <p className="text-ink-700 text-xs mt-3">{riskMap.proximity_rule.description}</p>
          )}
        </div>
      )}
    </div>
  )
}
