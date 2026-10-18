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

function toLatLngCoords(geojsonCoords: any): LatLngTuple[] {
  if (!geojsonCoords || !Array.isArray(geojsonCoords)) return []
  return geojsonCoords
    .map((c: any) => {
      if (typeof c === 'string') {
        const parts = c.trim().split(/\s+/)
        if (parts.length >= 2) {
          const lon = parseFloat(parts[0])
          const lat = parseFloat(parts[1])
          if (isFinite(lat) && isFinite(lon)) return [lat, lon] as LatLngTuple
        }
        return null
      }
      if (Array.isArray(c) && c.length >= 2) {
        const lon = Number(c[0])
        const lat = Number(c[1])
        if (isFinite(lat) && isFinite(lon)) return [lat, lon] as LatLngTuple
      }
      return null
    })
    .filter((c): c is LatLngTuple => c !== null)
}

/** Study-area boundary — a rectangular scoping frame, not an official
 * administrative polygon (documented in the backend). */
export function StudyAreaBoundaryLayer({ boundary }: { boundary: any }) {
  if (!boundary || !boundary.geometry || !boundary.geometry.coordinates || !boundary.geometry.coordinates[0]) {
    return null
  }
  const coords = toLatLngCoords(boundary.geometry.coordinates[0])
  if (coords.length === 0) return null
  return (
    <Polygon
      positions={coords}
      pathOptions={{ color: '#2DD4BF', weight: 1.5, fillOpacity: 0.02, dashArray: '4 4' }}
    />
  )
}

/** Waterway / River centerline, loaded dynamically or from local GeoJSON. */
export function RiverLayer({ river }: { river: any }) {
  if (!river || !river.geometry || !river.geometry.coordinates) return null
  const geom = river.geometry
  const name = river.properties?.name ?? 'Study Waterway'

  if (geom.type === 'MultiLineString') {
    if (!Array.isArray(geom.coordinates)) return null
    return (
      <>
        {geom.coordinates.map((line: any, idx: number) => {
          const coords = toLatLngCoords(line)
          if (coords.length === 0) return null
          return (
            <Polyline key={idx} positions={coords} pathOptions={{ color: '#3B82C4', weight: 3 }}>
              <Tooltip sticky>{name}</Tooltip>
            </Polyline>
          )
        })}
      </>
    )
  }

  const coords = toLatLngCoords(geom.coordinates)
  if (coords.length === 0) return null
  return (
    <Polyline positions={coords} pathOptions={{ color: '#3B82C4', weight: 3 }}>
      <Tooltip sticky>{name}</Tooltip>
    </Polyline>
  )
}

/** Flood-risk zone grid (spatial model). Colours by risk level when a risk
 * map is available; otherwise renders neutral geometry-only outlines.
 */
export function RiskZoneLayer({
  zones,
  riskLookup,
  onZoneClick,
  onZoneHover,
}: {
  zones?: RiskZone[] | null
  riskLookup?: Map<string, RiskZone>
  onZoneClick?: (zoneId: string) => void
  onZoneHover?: (zone: RiskZone | null, latLng?: LatLngTuple) => void
}) {
  if (!zones || !Array.isArray(zones)) return null

  return (
    <>
      {zones.map((z) => {
        if (!z || !z.bounds || !isFinite(z.bounds.min_lat) || !isFinite(z.bounds.min_lon) || !isFinite(z.bounds.max_lat) || !isFinite(z.bounds.max_lon)) {
          return null
        }
        const risk = riskLookup?.get(z.zone_id)
        const rf = risk?.risk_factors
        const color = risk ? RISK_COLORS[risk.risk_level] : '#3B4857'
        const boundsCoords: LatLngTuple[] = [
          [z.bounds.min_lat, z.bounds.min_lon], [z.bounds.min_lat, z.bounds.max_lon],
          [z.bounds.max_lat, z.bounds.max_lon], [z.bounds.max_lat, z.bounds.min_lon],
        ]
        const centerLat = (z.bounds.min_lat + z.bounds.max_lat) / 2
        const centerLon = (z.bounds.min_lon + z.bounds.max_lon) / 2

        return (
          <Polygon
            key={z.zone_id}
            positions={boundsCoords}
            pathOptions={{ color, weight: 1, fillOpacity: risk ? 0.11 : 0.02 }}
            eventHandlers={{
              click: () => onZoneClick?.(z.zone_id),
              mouseover: () => onZoneHover?.(risk || z, [centerLat, centerLon]),
              mouseout: () => onZoneHover?.(null),
            }}
          />
        )
      })}
    </>
  )
}
