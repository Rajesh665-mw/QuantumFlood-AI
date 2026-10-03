import { Polygon, Polyline, Popup, Tooltip } from 'react-leaflet'
import type { LatLngTuple } from 'leaflet'
import type { RiskZone } from '../../types'

export const RISK_COLORS: Record<string, string> = {
  LOW: '#4E9A6B', MODERATE: '#C99A3B', HIGH: '#D9803E', CRITICAL: '#D2504A',
}

const BAND_LABELS: Record<string, string> = {
  NEAR_RIVER: 'Near River',
  MID_RANGE: 'Mid Range',
  FAR_FROM_RIVER: 'Far from River',
}

function toLatLngCoords(geojsonCoords: [number, number][]): LatLngTuple[] {
  return geojsonCoords.map(([lon, lat]) => [lat, lon] as LatLngTuple)
}

/** Study-area boundary — a rectangular scoping frame, not an official
 * administrative polygon (documented in the backend). */
export function StudyAreaBoundaryLayer({ boundary }: { boundary: any }) {
  const coords = toLatLngCoords(boundary.geometry.coordinates[0])
  return (
    <Polygon
      positions={coords}
      pathOptions={{ color: '#2DD4BF', weight: 1.5, fillOpacity: 0.02, dashArray: '4 4' }}
    />
  )
}

/** Krishna River centerline, loaded from the project's local GeoJSON. */
export function RiverLayer({ river }: { river: any }) {
  const coords = toLatLngCoords(river.geometry.coordinates)
  return (
    <Polyline positions={coords} pathOptions={{ color: '#3B82C4', weight: 3 }}>
      <Tooltip sticky>{river.properties?.name ?? 'River'}</Tooltip>
    </Polyline>
  )
}

/** Flood-risk zone grid (spatial model). Colours by risk level when a risk
 * map is available; otherwise renders neutral geometry-only outlines.
 *
 * Popup content includes:
 *   - Zone ID, risk level, risk score, distance to river
 *   - Contributing factor breakdown (proximity factor, effective values,
 *     driving factor, explanation) when risk_factors are available
 *   - Spatial attenuation model label
 */
export function RiskZoneLayer({
  zones, riskLookup, onZoneClick,
}: {
  zones: RiskZone[]
  riskLookup?: Map<string, RiskZone>
  onZoneClick?: (zoneId: string) => void
}) {
  return (
    <>
      {zones.map((z) => {
        const risk = riskLookup?.get(z.zone_id)
        const color = risk ? RISK_COLORS[risk.risk_level] : '#3B4857'
        const boundsCoords: LatLngTuple[] = [
          [z.bounds.min_lat, z.bounds.min_lon], [z.bounds.min_lat, z.bounds.max_lon],
          [z.bounds.max_lat, z.bounds.max_lon], [z.bounds.max_lat, z.bounds.min_lon],
        ]
        const rf = risk?.risk_factors
        return (
          <Polygon
            key={z.zone_id}
            positions={boundsCoords}
            pathOptions={{ color, weight: 1, fillOpacity: risk ? 0.28 : 0.06 }}
            eventHandlers={onZoneClick ? { click: () => onZoneClick(z.zone_id) } : undefined}
          >
            <Popup maxWidth={320}>
              <div className="font-mono text-xs leading-relaxed" style={{ minWidth: 220 }}>
                <div className="font-semibold mb-1 text-sm">{z.zone_id}</div>
                {risk ? (
                  <>
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="inline-block w-2.5 h-2.5 rounded-full"
                        style={{ background: RISK_COLORS[risk.risk_level] }}
                      />
                      <span>Risk: <strong>{risk.risk_level}</strong> (score {risk.risk_score})</span>
                    </div>
                    <div className="mb-1">Distance to river: {risk.distance_to_river_km.toFixed(2)} km</div>

                    {rf && (
                      <div className="mt-2 pt-2 border-t border-gray-300" style={{ borderColor: '#ddd' }}>
                        <div className="font-semibold mb-1 text-[10px] uppercase tracking-wider opacity-70">
                          Risk Factor Breakdown
                        </div>
                        <div className="space-y-0.5">
                          <div>Proximity: <strong>{BAND_LABELS[rf.proximity_band] ?? rf.proximity_band}</strong> (factor {rf.river_proximity_factor})</div>
                          <div>Eff. water level: {rf.effective_water_level_m} m <span className="opacity-60">(base {rf.base_water_level_m} m)</span></div>
                          <div>Eff. inflow: {rf.effective_inflow_ktcmd} kTCM/d <span className="opacity-60">(base {rf.base_inflow_ktcmd})</span></div>
                          <div>Rainfall: {rf.rainfall_mm_24h} mm <span className="opacity-60">(uniform)</span></div>
                          <div className="mt-1 opacity-80">Driver: {rf.driving_factor.replace(/_/g, ' ')}</div>
                          <div className="opacity-60 text-[10px] mt-1">{rf.attenuation_model.replace(/_/g, ' ').toLowerCase()}</div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-gray-500">No risk classification yet</div>
                )}
                <div className="mt-1">Distance to river: {z.distance_to_river_km.toFixed(2)} km</div>
              </div>
            </Popup>
          </Polygon>
        )
      })}
    </>
  )
}
