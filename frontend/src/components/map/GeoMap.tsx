import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import { LayersControl as RLLayersControl } from 'react-leaflet'
import type { ReactNode } from 'react'
import type { LatLngBoundsExpression, LatLngTuple } from 'leaflet'
import type { MapConfig, MaxBounds } from '../../types'

/**
 * GeoMap — the single reusable map shell for QuantumFlood AI.
 *
 * Every map page (Flood Risk Map, Sensor Optimisation, Network & Coverage)
 * renders through this component so all maps share:
 *  - the same tile provider + attribution
 *  - the same zoom constraints (min/max)
 *  - the same maxBounds + viscosity (prevents panning/zooming into a
 *    repeated/looping world view — see Part 1 of the map upgrade)
 *  - tile wrapping disabled (noWrap)
 *  - a Reset View control
 *  - an optional Leaflet layer-toggle control
 *
 * `mapConfig` and `bounds` come from GET /api/map/layers — the backend is
 * the single source of truth for map display configuration, so no page
 * hardcodes its own zoom/bounds behaviour.
 */

export function boundsToLeaflet(bounds: MaxBounds): LatLngBoundsExpression {
  return [
    [bounds.south_west.lat, bounds.south_west.lon],
    [bounds.north_east.lat, bounds.north_east.lon],
  ]
}

export default function GeoMap({
  mapConfig,
  bounds,
  center,
  height = '520px',
  children,
}: {
  mapConfig: MapConfig
  bounds: MaxBounds
  center: LatLngTuple
  height?: string
  children?: ReactNode
}) {
  const leafletBounds = boundsToLeaflet(bounds)

  return (
    <div style={{ height }} className="rounded overflow-hidden relative">
      <MapContainer
        center={center}
        zoom={mapConfig.default_zoom}
        minZoom={mapConfig.min_zoom}
        maxZoom={mapConfig.max_zoom}
        maxBounds={leafletBounds}
        maxBoundsViscosity={mapConfig.max_bounds_viscosity}
        worldCopyJump={mapConfig.world_copy_jump}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url={mapConfig.tile_url}
          subdomains={mapConfig.tile_subdomains}
          attribution={mapConfig.tile_attribution}
          noWrap={mapConfig.no_wrap}
        />

        {children}

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
      onClick={() => map.flyToBounds(bounds, { padding: [24, 24], duration: 0.6 })}
      className="absolute z-[1000] bottom-3 right-3 bg-base-800/95 border border-base-600 text-ink-100 text-xs font-mono px-3 py-1.5 rounded hover:bg-base-700 hover:border-signal-teal/50 transition-colors shadow-lg"
      aria-label="Reset map view to study area"
    >
      ⤾ Reset View
    </button>
  )
}
