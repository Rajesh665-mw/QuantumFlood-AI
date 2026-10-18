import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import { LayersControl as RLLayersControl } from 'react-leaflet'
import type { ReactNode } from 'react'
import type { LatLngBoundsExpression, LatLngTuple } from 'leaflet'
import type { MapConfig, MaxBounds } from '../../types'

/**
 * Permanent, global English-label basemap: Esri World Street Map.
 * Renders English/Latin geographic labels globally across all continents without API keys.
 */
export const ESRI_ENGLISH_STREETS_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'

export const ESRI_ATTRIBUTION =
  'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, METI, TomTom'

export interface FlyCommand {
  id: number
  bounds: LatLngBoundsExpression
  center?: LatLngTuple
  duration?: number
}

/**
 * Universal bounds normalizer: safely converts MaxBounds, BoundingBox, or center
 * coordinates into a strictly ordered, finite LatLngBoundsExpression [[minLat, minLon], [maxLat, maxLon]].
 * Completely prevents Leaflet NaN or inverted bounds errors.
 */
export function boundsToLeaflet(
  bounds?: any | null,
  center?: LatLngTuple | { lat: number; lon: number } | null
): LatLngBoundsExpression {
  // Case 1: MaxBounds object { south_west: { lat, lon }, north_east: { lat, lon } }
  if (bounds && bounds.south_west && bounds.north_east) {
    const swLat = Number(bounds.south_west.lat)
    const swLon = Number(bounds.south_west.lon)
    const neLat = Number(bounds.north_east.lat)
    const neLon = Number(bounds.north_east.lon)

    if (isFinite(swLat) && isFinite(swLon) && isFinite(neLat) && isFinite(neLon)) {
      return [
        [Math.min(swLat, neLat), Math.min(swLon, neLon)],
        [Math.max(swLat, neLat), Math.max(swLon, neLon)],
      ]
    }
  }

  // Case 2: BoundingBox object { min_lat, max_lat, min_lon, max_lon }
  if (bounds && (bounds.min_lat !== undefined || bounds.max_lat !== undefined)) {
    const minLat = Number(bounds.min_lat)
    const maxLat = Number(bounds.max_lat)
    const minLon = Number(bounds.min_lon)
    const maxLon = Number(bounds.max_lon)

    if (isFinite(minLat) && isFinite(maxLat) && isFinite(minLon) && isFinite(maxLon)) {
      return [
        [Math.min(minLat, maxLat), Math.min(minLon, maxLon)],
        [Math.max(minLat, maxLat), Math.max(minLon, maxLon)],
      ]
    }
  }

  // Case 3: Already an array [[lat1, lon1], [lat2, lon2]]
  if (Array.isArray(bounds) && bounds.length >= 2 && Array.isArray(bounds[0]) && Array.isArray(bounds[1])) {
    const p1Lat = Number(bounds[0][0])
    const p1Lon = Number(bounds[0][1])
    const p2Lat = Number(bounds[1][0])
    const p2Lon = Number(bounds[1][1])
    if (isFinite(p1Lat) && isFinite(p1Lon) && isFinite(p2Lat) && isFinite(p2Lon)) {
      return [
        [Math.min(p1Lat, p2Lat), Math.min(p1Lon, p2Lon)],
        [Math.max(p1Lat, p2Lat), Math.max(p1Lon, p2Lon)],
      ]
    }
  }

  // Case 4: Derive bounding box from center coordinate (±0.06 deg buffer ~ 6.5km)
  if (center) {
    const cLat = Array.isArray(center) ? Number(center[0]) : Number(center.lat)
    const cLon = Array.isArray(center) ? Number(center[1]) : Number(center.lon)
    if (isFinite(cLat) && isFinite(cLon)) {
      return [
        [cLat - 0.06, cLon - 0.06],
        [cLat + 0.06, cLon + 0.06],
      ]
    }
  }

  // Fallback: Default Vijayawada Corridor baseline
  return [
    [16.32, 80.43],
    [16.68, 80.84],
  ]
}

/**
 * Dedicated Leaflet camera controller: handles container size invalidation,
 * monotonic fly commands, and camera animation lifecycle without remount races.
 */
function MapCameraController({
  flyCommand,
  onFlyComplete,
  defaultBounds,
}: {
  flyCommand?: FlyCommand | null
  onFlyComplete?: (commandId: number) => void
  defaultBounds: LatLngBoundsExpression
}) {
  const map = useMap()
  const lastExecutedIdRef = useRef<number>(-1)

  // Ensure Leaflet has computed accurate container pixel dimensions on mount and resize
  useEffect(() => {
    const invalidate = () => {
      try {
        map.invalidateSize({ animate: false })
      } catch {}
    }
    const t1 = setTimeout(invalidate, 60)
    const t2 = setTimeout(invalidate, 250)
    const t3 = setTimeout(invalidate, 600)

    const container = map.getContainer()
    let observer: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined' && container) {
      observer = new ResizeObserver(() => {
        invalidate()
      })
      observer.observe(container)
    }
    window.addEventListener('resize', invalidate)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
      observer?.disconnect()
      window.removeEventListener('resize', invalidate)
    }
  }, [map])

  // Execute fly command whenever an explicit new command is issued
  useEffect(() => {
    if (!flyCommand) return
    if (flyCommand.id === lastExecutedIdRef.current) return
    lastExecutedIdRef.current = flyCommand.id

    const cmdId = flyCommand.id
    const targetBounds = flyCommand.bounds || defaultBounds
    let finished = false

    const notifyComplete = () => {
      if (finished) return
      finished = true
      onFlyComplete?.(cmdId)
    }

    // Step 1: Invalidate map viewport size to account for container visibility/layout changes
    try {
      map.invalidateSize({ animate: false })
    } catch {}

    const executeFly = () => {
      try {
        const size = map.getSize()
        if (!size || size.x === 0 || size.y === 0) {
          // If container has not yet painted dimensions, retry on next frame
          requestAnimationFrame(() => {
            try {
              map.invalidateSize({ animate: false })
              map.flyToBounds(targetBounds, {
                padding: [36, 36],
                duration: flyCommand.duration || 1.1,
                maxZoom: 14,
              })
              map.once('moveend', notifyComplete)
            } catch {
              notifyComplete()
            }
          })
          return
        }

        map.flyToBounds(targetBounds, {
          padding: [36, 36],
          duration: flyCommand.duration || 1.1,
          maxZoom: 14,
        })
        map.once('moveend', notifyComplete)
      } catch (e) {
        console.warn('[GeoMap] flyToBounds execution fallback:', e)
        notifyComplete()
      }
    }

    executeFly()

    // Safety timeout: guaranteed transition even if moveend doesn't fire
    const safetyTimeout = setTimeout(notifyComplete, (flyCommand.duration || 1.1) * 1000 + 350)
    return () => {
      clearTimeout(safetyTimeout)
      map.off('moveend', notifyComplete)
    }
  }, [flyCommand, map, defaultBounds, onFlyComplete])

  return null
}

export default function GeoMap({
  mapConfig,
  bounds,
  center,
  height = '520px',
  children,
  onTilesLoaded,
  onTileError,
  flyCommand,
  onFlyComplete,
}: {
  mapConfig?: MapConfig | null
  bounds?: any | null
  center?: LatLngTuple | { lat: number; lon: number } | null
  height?: string
  children?: ReactNode
  onTilesLoaded?: () => void
  onTileError?: () => void
  flyCommand?: FlyCommand | null
  onFlyComplete?: (commandId: number) => void
}) {
  const safeLat = center
    ? Array.isArray(center)
      ? Number(center[0])
      : Number(center.lat)
    : 16.5061
  const safeLon = center
    ? Array.isArray(center)
      ? Number(center[1])
      : Number(center.lon)
    : 80.6050

  const safeCenter: LatLngTuple = [
    isFinite(safeLat) ? safeLat : 16.5061,
    isFinite(safeLon) ? safeLon : 80.6050,
  ]
  const leafletBounds = boundsToLeaflet(bounds, safeCenter)

  const cfg = mapConfig || {
    default_zoom: 12,
    min_zoom: 3,
    max_zoom: 17,
    tile_url: ESRI_ENGLISH_STREETS_URL,
    tile_subdomains: [],
    tile_attribution: ESRI_ATTRIBUTION,
    no_wrap: true,
    world_copy_jump: false,
    max_bounds_viscosity: 0.8,
  }

  const tileUrl = cfg.tile_url || ESRI_ENGLISH_STREETS_URL
  const tileSubdomains = cfg.tile_subdomains || []
  const tileAttribution = cfg.tile_attribution || ESRI_ATTRIBUTION

  return (
    <div style={{ height, width: '100%' }} className="rounded overflow-hidden relative bg-base-900">
      <MapContainer
        key="quantumflood-map-viewport"
        center={safeCenter}
        zoom={cfg.default_zoom || 12}
        minZoom={cfg.min_zoom || 3}
        maxZoom={cfg.max_zoom || 17}
        worldCopyJump={cfg.world_copy_jump ?? false}
        style={{ height: '100%', width: '100%', background: '#161F2C' }}
      >
        <TileLayer
          url={tileUrl}
          subdomains={tileSubdomains}
          attribution={tileAttribution}
          maxZoom={cfg.max_zoom || 18}
          noWrap={cfg.no_wrap ?? true}
          eventHandlers={{
            load: () => {
              onTilesLoaded?.()
            },
            tileerror: () => {
              onTileError?.()
            },
          }}
        />

        {children}

        <MapCameraController
          flyCommand={flyCommand}
          onFlyComplete={onFlyComplete}
          defaultBounds={leafletBounds}
        />
        <ResetViewControl bounds={leafletBounds} />
      </MapContainer>
    </div>
  )
}

/** Re-exports for composeable layer control */
export const LayersControl = RLLayersControl
export const LayersOverlay = RLLayersControl.Overlay
export const BaseLayer = RLLayersControl.BaseLayer

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
