import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import { LayersControl as RLLayersControl } from 'react-leaflet'
import type { ReactNode } from 'react'
import type { LatLngBoundsExpression, LatLngTuple } from 'leaflet'
import type { MapConfig, MaxBounds } from '../../types'

export function boundsToLeaflet(bounds?: MaxBounds | null, center?: LatLngTuple | null): LatLngBoundsExpression {
  if (bounds && bounds.south_west && bounds.north_east) {
    const swLat = Number(bounds.south_west.lat)
    const swLon = Number(bounds.south_west.lon)
    const neLat = Number(bounds.north_east.lat)
    const neLon = Number(bounds.north_east.lon)

    if (isFinite(swLat) && isFinite(swLon) && isFinite(neLat) && isFinite(neLon)) {
      return [
        [swLat, swLon],
        [neLat, neLon],
      ]
    }
  }

  if (center && isFinite(center[0]) && isFinite(center[1])) {
    const cLat = Number(center[0])
    const cLon = Number(center[1])
    return [
      [cLat - 0.08, cLon - 0.08],
      [cLat + 0.08, cLon + 0.08],
    ]
  }

  return [
    [16.32, 80.43],
    [16.68, 80.84],
  ]
}

function MapRecenterHelper({ bounds, center }: { bounds: LatLngBoundsExpression; center: LatLngTuple }) {
  const map = useMap()
  const isFirstMountRef = useRef(true)
  const prevCenterKeyRef = useRef(`${center[0].toFixed(4)},${center[1].toFixed(4)}`)

  useEffect(() => {
    // On initial mount: map is already initialized with center & zoom by MapContainer.
    // Trigger invalidateSize after paint so Leaflet recalculates pixel boundaries cleanly.
    if (isFirstMountRef.current) {
      isFirstMountRef.current = false
      const timer = setTimeout(() => {
        try {
          map.invalidateSize()
        } catch {
          // ignore
        }
      }, 100)
      return () => clearTimeout(timer)
    }

    // On subsequent prop changes: only fly to bounds if center has meaningfully changed
    const currentCenterKey = `${center[0].toFixed(4)},${center[1].toFixed(4)}`
    if (prevCenterKeyRef.current !== currentCenterKey) {
      prevCenterKeyRef.current = currentCenterKey
      const timer = setTimeout(() => {
        try {
          map.invalidateSize()
          const size = map.getSize()
          if (size && size.x > 0 && size.y > 0) {
            map.flyToBounds(bounds, { padding: [24, 24], duration: 0.7 })
          }
        } catch (e) {
          console.warn('Map flyToBounds skipped:', e)
        }
      }, 50)
      return () => clearTimeout(timer)
    }
  }, [map, center[0], center[1], JSON.stringify(bounds)])

  return null
}

export default function GeoMap({
  mapConfig,
  bounds,
  center,
  height = '520px',
  children,
}: {
  mapConfig?: MapConfig | null
  bounds?: MaxBounds | null
  center?: LatLngTuple | null
  height?: string
  children?: ReactNode
}) {
  const safeLat = center && isFinite(center[0]) ? Number(center[0]) : 16.5061
  const safeLon = center && isFinite(center[1]) ? Number(center[1]) : 80.6050
  const safeCenter: LatLngTuple = [safeLat, safeLon]
  const leafletBounds = boundsToLeaflet(bounds, safeCenter)

  const cfg = mapConfig || {
    default_zoom: 12,
    min_zoom: 4,
    max_zoom: 17,
    tile_url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    tile_subdomains: ['a', 'b', 'c'],
    tile_attribution: '&copy; OpenStreetMap contributors',
    no_wrap: true,
    world_copy_jump: false,
    max_bounds_viscosity: 0.8,
  }

  const containerKey = `map-${safeLat.toFixed(3)}-${safeLon.toFixed(3)}`

  return (
    <div style={{ height, width: '100%' }} className="rounded overflow-hidden relative bg-base-900">
      <MapContainer
        key={containerKey}
        center={safeCenter}
        zoom={cfg.default_zoom || 12}
        minZoom={cfg.min_zoom || 4}
        maxZoom={cfg.max_zoom || 17}
        maxBounds={leafletBounds}
        maxBoundsViscosity={cfg.max_bounds_viscosity ?? 0.8}
        worldCopyJump={cfg.world_copy_jump ?? false}
        style={{ height: '100%', width: '100%', background: '#161F2C' }}
      >
        <TileLayer
          url={cfg.tile_url || 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'}
          subdomains={cfg.tile_subdomains || ['a', 'b', 'c']}
          attribution={cfg.tile_attribution || '&copy; OpenStreetMap contributors'}
          noWrap={cfg.no_wrap ?? true}
        />

        {children}

        <MapRecenterHelper bounds={leafletBounds} center={safeCenter} />
        <ResetViewControl bounds={leafletBounds} />
      </MapContainer>
    </div>
  )
}

/** Re-exports so pages can compose layer toggles without importing
 * react-leaflet directly (keeps the map system's public surface in one
 * place). Wrap toggleable layer groups in <LayersControl><LayersOverlay>. */
export const LayersControl = RLLayersControl
export const LayersOverlay = RLLayersControl.Overlay

function ResetViewControl({ bounds }: { bounds: LatLngBoundsExpression }) {
  const map = useMap()
  return (
    <button
      type="button"
      onClick={() => {
        try {
          map.invalidateSize()
          const size = map.getSize()
          if (size && size.x > 0 && size.y > 0) {
            map.flyToBounds(bounds, { padding: [24, 24], duration: 0.6 })
          }
        } catch (e) {
          console.warn('Reset view failed:', e)
        }
      }}
      className="absolute z-[1000] bottom-3 right-3 bg-base-800/95 border border-base-600 text-ink-100 text-xs font-mono px-3 py-1.5 rounded hover:bg-base-700 hover:border-signal-teal/50 transition-colors shadow-lg"
      aria-label="Reset map view to study area"
    >
      ⤾ Reset View
    </button>
  )
}
