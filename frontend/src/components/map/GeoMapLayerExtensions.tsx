import { Fragment } from 'react'
import { CircleMarker, Polyline, Popup, Tooltip } from 'react-leaflet'
import type { LatLngTuple } from 'leaflet'
import type {
  SafeLocation,
  EvacuationRoutePlan,
  RedeploymentAction,
  CommNode,
  ZoneResourceAllocation,
} from '../../types'

/**
 * Visual Layer for Candidate Lower-Risk Safe Locations
 */
export function SafeLocationMarkersLayer({
  locations,
  onLocationClick,
}: {
  locations?: SafeLocation[] | null
  onLocationClick?: (loc: SafeLocation) => void
}) {
  if (!locations || !Array.isArray(locations)) return null

  return (
    <>
      {locations.map((loc) => {
        if (!loc || !isFinite(loc.lat) || !isFinite(loc.lon)) return null
        const score = loc.recommendation_score ?? 50
        const color = score >= 75 ? '#10B981' : score >= 55 ? '#2DD4BF' : '#F59E0B'
        return (
          <CircleMarker
            key={loc.id}
            center={[loc.lat, loc.lon]}
            radius={8}
            pathOptions={{
              color: '#0B121A',
              weight: 2,
              fillColor: color,
              fillOpacity: 0.9,
            }}
            eventHandlers={onLocationClick ? { click: () => onLocationClick(loc) } : undefined}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <div className="font-mono text-xs">
                <strong>{loc.name}</strong> ({score}/100)
                <br />
                <span className="text-[10px] text-ink-500">{loc.category?.replace(/_/g, ' ') ?? 'Facility'}</span>
              </div>
            </Tooltip>
            <Popup maxWidth={300}>
              <div className="font-mono text-xs leading-relaxed">
                <div className="font-bold text-sm text-ink-100">{loc.name}</div>
                <div className="text-[11px] text-signal-teal mt-0.5">{loc.status_label}</div>
                <div className="mt-2 text-[11px] text-ink-300">
                  <div>Recommendation Score: <strong>{score} / 100</strong></div>
                  <div>Elevation: <strong>{loc.elevation_m} m</strong></div>
                  <div>Distance to river: <strong>{loc.distance_to_river_km} km</strong></div>
                  <div>Assigned Zone: <strong>{loc.assigned_zone_id}</strong> ({loc.modelled_risk_level} risk)</div>
                  <div>Road Access: <strong>{loc.primary_road_access}</strong></div>
                  <div>Capacity Status: <strong className="text-amber-400">{loc.capacity_status}</strong></div>
                </div>
                <div className="mt-2 pt-2 border-t border-base-600 text-[10px] text-ink-400 italic">
                  {loc.explanation}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}

/**
 * Visual Layer for Dynamic Evacuation Routes
 */
export function EvacuationRouteLayer({
  primaryRoute,
  alternativeRoute,
  origin,
  destination,
}: {
  primaryRoute?: EvacuationRoutePlan | null
  alternativeRoute?: EvacuationRoutePlan | null
  origin?: { lat: number; lon: number; name: string } | null
  destination?: { lat: number; lon: number; name: string } | null
}) {
  const primaryCoords: LatLngTuple[] = (primaryRoute?.coordinates ?? [])
    .filter(([lon, lat]) => isFinite(lon) && isFinite(lat))
    .map(([lon, lat]) => [lat, lon] as LatLngTuple)

  const altCoords: LatLngTuple[] = (alternativeRoute?.coordinates ?? [])
    .filter(([lon, lat]) => isFinite(lon) && isFinite(lat))
    .map(([lon, lat]) => [lat, lon] as LatLngTuple)

  return (
    <>
      {/* Alternative Route */}
      {altCoords.length > 1 && (
        <Polyline
          positions={altCoords}
          pathOptions={{
            color: '#F59E0B',
            weight: 3.5,
            opacity: 0.7,
            dashArray: '6 6',
          }}
        >
          <Tooltip sticky>
            <div className="font-mono text-xs">
              Alternative Route (Shortest) · {alternativeRoute?.total_distance_km} km
            </div>
          </Tooltip>
        </Polyline>
      )}

      {/* Primary Route */}
      {primaryCoords.length > 1 && (
        <Polyline
          positions={primaryCoords}
          pathOptions={{
            color: '#2DD4BF',
            weight: 5,
            opacity: 0.95,
          }}
        >
          <Tooltip sticky>
            <div className="font-mono text-xs">
              Primary Evacuation Route · {primaryRoute?.total_distance_km} km · Risk score: {primaryRoute?.estimated_route_risk_score}
            </div>
          </Tooltip>
        </Polyline>
      )}

      {/* High-risk segments highlight */}
      {(primaryRoute?.segments ?? [])
        .filter((s) => s.is_high_risk && isFinite(s.start_coord?.lat) && isFinite(s.start_coord?.lon) && isFinite(s.end_coord?.lat) && isFinite(s.end_coord?.lon))
        .map((s) => (
          <Polyline
            key={s.edge_id}
            positions={[
              [s.start_coord.lat, s.start_coord.lon],
              [s.end_coord.lat, s.end_coord.lon],
            ]}
            pathOptions={{
              color: '#EF4444',
              weight: 6,
              opacity: 0.9,
            }}
          >
            <Tooltip sticky>
              <div className="font-mono text-xs text-red-300">
                Warning: High-Risk Segment ({s.road_name})
              </div>
            </Tooltip>
          </Polyline>
        ))}

      {/* Origin Pin */}
      {origin && isFinite(origin.lat) && isFinite(origin.lon) && (
        <CircleMarker
          center={[origin.lat, origin.lon]}
          radius={7}
          pathOptions={{ color: '#FFFFFF', weight: 2, fillColor: '#EF4444', fillOpacity: 1 }}
        >
          <Tooltip direction="top" permanent>
            <span className="font-mono text-[10px] font-bold">Origin: {origin.name}</span>
          </Tooltip>
        </CircleMarker>
      )}

      {/* Destination Pin */}
      {destination && isFinite(destination.lat) && isFinite(destination.lon) && (
        <CircleMarker
          center={[destination.lat, destination.lon]}
          radius={7}
          pathOptions={{ color: '#FFFFFF', weight: 2, fillColor: '#10B981', fillOpacity: 1 }}
        >
          <Tooltip direction="top" permanent>
            <span className="font-mono text-[10px] font-bold">Dest: {destination.name}</span>
          </Tooltip>
        </CircleMarker>
      )}
    </>
  )
}

/**
 * Visual Layer for Adaptive Sensor Redeployment Transitions
 */
export function SensorRedeploymentLayer({
  actions,
}: {
  actions?: RedeploymentAction[] | null
}) {
  if (!actions || !Array.isArray(actions)) return null

  return (
    <>
      {actions.map((act) => {
        if (act.action === 'KEEP' && act.current_site && isFinite(act.current_site.lat) && isFinite(act.current_site.lon)) {
          return (
            <CircleMarker
              key={`keep-${act.sensor_id}`}
              center={[act.current_site.lat, act.current_site.lon]}
              radius={6}
              pathOptions={{ color: '#FFFFFF', weight: 1.5, fillColor: '#10B981', fillOpacity: 0.9 }}
            >
              <Tooltip>
                <div className="font-mono text-xs">
                  <strong>KEEP:</strong> Sensor {act.sensor_id}
                </div>
              </Tooltip>
            </CircleMarker>
          )
        }

        if (
          act.action === 'RELOCATE' &&
          act.current_site &&
          act.target_site &&
          isFinite(act.current_site.lat) &&
          isFinite(act.current_site.lon) &&
          isFinite(act.target_site.lat) &&
          isFinite(act.target_site.lon)
        ) {
          const arrowCoords: LatLngTuple[] = [
            [act.current_site.lat, act.current_site.lon],
            [act.target_site.lat, act.target_site.lon],
          ]
          return (
            <Fragment key={`reloc-grp-${act.sensor_id}`}>
              {/* Old site */}
              <CircleMarker
                center={[act.current_site.lat, act.current_site.lon]}
                radius={5}
                pathOptions={{ color: '#F59E0B', weight: 1.5, fillColor: '#0B121A', fillOpacity: 0.8 }}
              >
                <Tooltip>
                  <div className="font-mono text-xs">
                    Original Site: {act.current_site.candidate_id}
                  </div>
                </Tooltip>
              </CircleMarker>

              {/* Movement Vector */}
              <Polyline
                positions={arrowCoords}
                pathOptions={{ color: '#2DD4BF', weight: 2.5, dashArray: '4 4' }}
              >
                <Tooltip sticky>
                  <div className="font-mono text-xs">
                    Relocation vector ({act.distance_km} km)
                  </div>
                </Tooltip>
              </Polyline>

              {/* New target site */}
              <CircleMarker
                center={[act.target_site.lat, act.target_site.lon]}
                radius={7}
                pathOptions={{ color: '#FFFFFF', weight: 2, fillColor: '#2DD4BF', fillOpacity: 1 }}
              >
                <Tooltip>
                  <div className="font-mono text-xs">
                    <strong>RELOCATED TO:</strong> {act.target_site.candidate_id}
                  </div>
                </Tooltip>
              </CircleMarker>
            </Fragment>
          )
        }

        if (act.action === 'ADD' && act.target_site && isFinite(act.target_site.lat) && isFinite(act.target_site.lon)) {
          return (
            <CircleMarker
              key={`add-${act.sensor_id}`}
              center={[act.target_site.lat, act.target_site.lon]}
              radius={6}
              pathOptions={{ color: '#FFFFFF', weight: 1.5, fillColor: '#3B82F6', fillOpacity: 1 }}
            >
              <Tooltip>
                <div className="font-mono text-xs">
                  <strong>ADD:</strong> New sensor {act.sensor_id}
                </div>
              </Tooltip>
            </CircleMarker>
          )
        }

        return null
      })}
    </>
  )
}

/**
 * Visual Layer for Network Resilience (Surviving vs Failed Comm Nodes & Links)
 */
export function NetworkResilienceLayer({
  survivingNodes,
  failedNodes,
  activeConnections,
  severedConnections,
  recoveryNode,
}: {
  survivingNodes?: CommNode[] | null
  failedNodes?: CommNode[] | null
  activeConnections?: { sensor_id: string; comm_node_id: string; distance_km: number; status: string }[] | null
  severedConnections?: { sensor_id: string; comm_node_id: string; distance_km: number; status: string }[] | null
  recoveryNode?: {
    lat: number
    lon: number
    recovery_node_id: string
    candidate_id: string
    reconnected_count: number
  } | null
}) {
  return (
    <>
      {/* Surviving Nodes */}
      {(survivingNodes ?? []).map((n) => {
        if (!n || !isFinite(n.lat) || !isFinite(n.lon)) return null
        return (
          <CircleMarker
            key={n.comm_node_id}
            center={[n.lat, n.lon]}
            radius={8}
            pathOptions={{ color: '#FFFFFF', weight: 2, fillColor: '#10B981', fillOpacity: 1 }}
          >
            <Tooltip>
              <div className="font-mono text-xs">
                <strong>Node {n.comm_node_id}</strong> (ONLINE)
              </div>
            </Tooltip>
          </CircleMarker>
        )
      })}

      {/* Failed Nodes */}
      {(failedNodes ?? []).map((n) => {
        if (!n || !isFinite(n.lat) || !isFinite(n.lon)) return null
        return (
          <CircleMarker
            key={`fail-${n.comm_node_id}`}
            center={[n.lat, n.lon]}
            radius={9}
            pathOptions={{ color: '#EF4444', weight: 3, fillColor: '#0B121A', fillOpacity: 0.9 }}
          >
            <Tooltip direction="top">
              <div className="font-mono text-xs text-red-400 font-bold">
                FAILED NODE: {n.comm_node_id} (OFFLINE)
              </div>
            </Tooltip>
          </CircleMarker>
        )
      })}

      {/* Recovery Backup Relay Node */}
      {recoveryNode && isFinite(recoveryNode.lat) && isFinite(recoveryNode.lon) && (
        <CircleMarker
          center={[recoveryNode.lat, recoveryNode.lon]}
          radius={10}
          pathOptions={{ color: '#FBBF24', weight: 3, fillColor: '#2DD4BF', fillOpacity: 1 }}
        >
          <Tooltip direction="top" permanent>
            <div className="font-mono text-xs font-bold text-amber-300">
              RECOVERY RELAY: {recoveryNode.candidate_id} (+{recoveryNode.reconnected_count} reconnected)
            </div>
          </Tooltip>
        </CircleMarker>
      )}
    </>
  )
}

/**
 * Visual Layer for Emergency Resource Allocations Overlaid on Zones
 */
export function ResourceAllocationLayer({
  allocations,
}: {
  allocations?: ZoneResourceAllocation[] | null
}) {
  if (!allocations || !Array.isArray(allocations)) return null

  return (
    <>
      {allocations.map((a) => {
        if (!a || !a.centroid || !isFinite(a.centroid.lat) || !isFinite(a.centroid.lon)) return null
        return (
          <CircleMarker
            key={`res-alloc-${a.zone_id}`}
            center={[a.centroid.lat, a.centroid.lon]}
            radius={11}
            pathOptions={{
              color: '#FFFFFF',
              weight: 2,
              fillColor: '#8B5CF6',
              fillOpacity: 0.9,
            }}
          >
            <Tooltip direction="center" permanent>
              <span className="font-mono font-bold text-[10px] text-white">
                {a.total_units_allocated}u
              </span>
            </Tooltip>
            <Popup maxWidth={280}>
              <div className="font-mono text-xs leading-relaxed">
                <div className="font-bold text-sm text-ink-100">{a.zone_id} Resource Plan</div>
                <div className="text-[11px] text-purple-400 mt-0.5">
                  Priority Score: <strong>{a.priority_score}</strong> ({a.risk_level} Risk)
                </div>
                <div className="mt-2 text-[11px] text-ink-200">
                  {Object.entries(a.allocated_resources ?? {}).map(([res, count]) =>
                    count > 0 ? (
                      <div key={res}>
                        • {count} × {res.replace(/_/g, ' ')}
                      </div>
                    ) : null
                  )}
                </div>
                <div className="mt-2 pt-2 border-t border-base-600 text-[10px] text-ink-400">
                  {a.explanation}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        )
      })}
    </>
  )
}
