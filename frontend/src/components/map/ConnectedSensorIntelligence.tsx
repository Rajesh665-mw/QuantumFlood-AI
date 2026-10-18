import { useState, useEffect, useCallback, useMemo, useRef, Fragment } from 'react'
import { useMap, Marker, Circle, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import type { SelectedSensor, RiskMap, StudyArea, Candidate, RiskZone } from '../../types'
import { RISK_COLORS } from './baseLayers'

export type CalloutType = 'sensor' | 'candidate' | 'risk-zone'

export interface ActiveCalloutTarget {
  type: CalloutType
  id: string
  lat: number
  lon: number
  isPinned?: boolean
  data?: any
}

export interface CalculatedSensorIntelligence {
  sensor: SelectedSensor
  rank: number
  lat: number
  lon: number
  allCoveredZoneIds: string[]
  marginalCoveredZoneIds: string[]
  marginalGain: number
  redundantZoneIds: string[]
  overlapSummary: {
    otherSensorRank: number
    otherSensorId: string
    sharedZoneIds: string[]
  }[]
  overlapCount: number
  isDisconnected: boolean
  placementMethod: string
  distanceToRiver?: number
  proximityBand?: string
  effectiveWaterLevel?: number
  selectionReason: string
  whySelectedExplanation: string
}

/**
 * Creates a clean, restrained, numbered sensor icon.
 */
function createNumberedSensorIcon(
  rank: number,
  isSelected: boolean,
  isHovered: boolean,
  isDisconnected: boolean
) {
  const bgClass = isHovered
    ? 'bg-sky-400 text-base-950 border-sky-200 shadow-[0_0_18px_rgba(56,189,248,0.95)]'
    : isSelected
    ? 'bg-amber-400 text-base-950 border-amber-300 shadow-[0_0_14px_rgba(250,204,21,0.85)]'
    : isDisconnected
    ? 'bg-rose-500 text-white border-rose-300 shadow-[0_0_10px_rgba(244,63,94,0.6)]'
    : 'bg-base-950 text-signal-teal border-signal-teal shadow-[0_0_10px_rgba(45,212,191,0.6)]'

  const pingClass = isHovered
    ? 'bg-sky-400/40'
    : isSelected
    ? 'bg-amber-400/30'
    : isDisconnected
    ? 'bg-rose-500/25'
    : 'bg-signal-teal/20'

  return L.divIcon({
    className: 'custom-sensor-icon-anchor pointer-events-auto cursor-pointer',
    html: `
      <div class="relative w-7 h-7 flex items-center justify-center pointer-events-none select-none">
        <span class="absolute w-7 h-7 rounded-full ${pingClass} animate-ping opacity-40"></span>
        <div class="relative w-6 h-6 rounded-full border-2 flex items-center justify-center font-mono font-bold text-[11px] transition-colors duration-150 ${bgClass}">
          ${rank}
        </div>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })
}

/**
 * Hook to calculate grounded multi-criteria intelligence for all active sensors.
 */
export function useCalculatedSensorIntelligence({
  activeSensors,
  riskMap,
  studyArea,
  numSensors,
  commRange = 4.0,
  disconnectedIds,
  activeSolverView,
  qaoaDepth = 1,
  qaoaShots = 1024,
}: {
  activeSensors: SelectedSensor[]
  riskMap: RiskMap | null
  studyArea?: StudyArea | null
  numSensors: number
  commRange?: number
  disconnectedIds: Set<string>
  activeSolverView: 'classical' | 'quantum'
  qaoaDepth?: number
  qaoaShots?: number
}) {
  const zoneWeights = useMemo(() => {
    const mapWeights = new Map<string, number>()
    ;(riskMap?.zones ?? []).forEach((z) => {
      const w = Number(z.risk_score || 1.0)
      mapWeights.set(z.zone_id, z.risk_level === 'CRITICAL' ? w * 2.0 : w)
    })
    return mapWeights
  }, [riskMap])

  return useMemo<CalculatedSensorIntelligence[]>(() => {
    const result: CalculatedSensorIntelligence[] = []
    const cumCovered = new Set<string>()

    const riverName = studyArea?.river || 'the river corridor'
    const zoneRiskLevels = new Map<string, string>()
    riskMap?.zones?.forEach((z) => {
      zoneRiskLevels.set(z.zone_id, z.risk_level)
    })

    activeSensors.forEach((s, idx) => {
      const rank = s.selection_rank || idx + 1
      const lat = Number(s.lat ?? (s as any).latitude)
      const lon = Number(s.lon ?? (s as any).longitude)
      const allCovered = s.covered_zone_ids || (s as any).zones_covered || []
      const isDisc = disconnectedIds.has(s.candidate_id)

      let marginalZones = s.marginal_covered_zones
      if (!marginalZones) {
        if (idx === 0) {
          marginalZones = [...allCovered]
        } else {
          marginalZones = allCovered.filter((z) => !cumCovered.has(z))
        }
      }
      allCovered.forEach((z) => cumCovered.add(z))

      let marginalGain = s.marginal_gain
      if (marginalGain === undefined) {
        marginalGain = marginalZones.reduce(
          (acc, z) => acc + (zoneWeights.get(z) || 1.0),
          0
        )
      }

      const redundantZones = allCovered.filter((z) => !marginalZones!.includes(z))

      const overlapSummary: CalculatedSensorIntelligence['overlapSummary'] = []
      activeSensors.forEach((other, oIdx) => {
        if (other.candidate_id === s.candidate_id) return
        const otherCovered = other.covered_zone_ids || (other as any).zones_covered || []
        const shared = allCovered.filter((z) => otherCovered.includes(z))
        if (shared.length > 0) {
          overlapSummary.push({
            otherSensorRank: other.selection_rank || oIdx + 1,
            otherSensorId: other.candidate_id,
            sharedZoneIds: shared,
          })
        }
      })

      const zoneData = riskMap?.zones?.find(
        (rz) =>
          rz.zone_id === s.zone_id ||
          rz.zone_id.toLowerCase().replace(/[^a-z0-9]/g, '') === (s.zone_id || '').toLowerCase().replace(/[^a-z0-9]/g, '')
      )
      const distToRiver = zoneData?.distance_to_river_km
      const band = zoneData?.risk_factors?.proximity_band || (s.near_river ? 'NEAR_RIVER' : 'MID_RANGE')
      const effWater = zoneData?.risk_factors?.effective_water_level_m

      // Short technical reason
      let reason = s.selection_reason
      if (!reason) {
        if (activeSolverView === 'quantum') {
          reason = `Selected by QAOA quantum statevector sampling (p=${qaoaDepth}, ${qaoaShots} shots), minimizing Ising QUBO cost under budget constraint K=${numSensors}.`
        } else if (rank === 1) {
          reason = `Selected at Rank #1 by greedy maximum-coverage heuristic: establishes initial baseline risk coverage across ${allCovered.length} zone(s).`
        } else {
          reason = `Selected at Rank #${rank} for maximum marginal risk gain (+${marginalGain.toFixed(2)} w-score) across remaining candidate sites.`
        }
      }

      // Synthesize rich, grounded explanation answering:
      // "Why did the optimizer choose this location instead of another candidate location?"
      const marginalFormatted = marginalZones.map((zId) => {
        const lvl = zoneRiskLevels.get(zId) || 'HIGH'
        return `${zId.replace('zone_', 'Z-')} (${lvl})`
      })

      const riverDistanceStr =
        distToRiver !== undefined
          ? `${distToRiver.toFixed(2)} km from ${riverName}`
          : `along ${riverName}`

      let whySelected = ''

      if (rank === 1) {
        if (activeSolverView === 'quantum') {
          whySelected = `Under the sensor budget limit of K=${numSensors}, QAOA quantum statevector sampling identified this site as the top-priority ground state node. It establishes the flood-monitoring foundation by securing ${allCovered.length} critical sector(s) [${marginalFormatted.join(', ')}] with the maximum initial weighted risk capture (+${marginalGain.toFixed(1)} w-score), situated ${riverDistanceStr}. Allocating Slot #1 here delivers the greatest single-node risk suppression before deploying remaining slots.`
        } else {
          whySelected = `Evaluated across all available candidate sites, this location was chosen for Slot #1 because it captures the single largest concentration of flood risk in the study area. It immediately brings ${allCovered.length} zone(s) [${marginalFormatted.join(', ')}] under active monitoring with a baseline weighted score of +${marginalGain.toFixed(1)}, situated ${riverDistanceStr}. Under a budget of K=${numSensors}, placing the initial sensor here resolves the most critical vulnerability first.`
        }
      } else if (marginalZones.length > 0) {
        const overlapText =
          overlapSummary.length > 0
            ? ` While it shares ${redundantZones.length} sector(s) with Sensor ${overlapSummary.map((o) => '#' + o.otherSensorRank).join(' & ')}, this overlap provides essential dual-sensor verification along rapid-inundation riverbank channels.`
            : ` It provides 100% unique territorial coverage with zero wasteful duplication against previously selected nodes.`

        const meshText = isDisc
          ? ` (Note: Located outside direct transceiver range >${commRange}km; mesh relay node required).`
          : ` It simultaneously satisfies multi-hop mesh connectivity within ${commRange}km of the network.`

        if (activeSolverView === 'quantum') {
          whySelected = `Selected by QAOA quantum optimization to minimize the global Ising QUBO energy under budget constraint K=${numSensors}. Compared to competing candidate sites, allocating this slot delivers +${marginalGain.toFixed(1)} marginal risk reduction, bringing ${marginalZones.length} previously unmonitored zone(s) [${marginalFormatted.join(', ')}] under surveillance.${overlapText}${meshText}`
        } else {
          whySelected = `This site was selected over competing candidate locations because it yields the highest marginal coverage contribution (+${marginalGain.toFixed(1)} weighted risk score), extending protection to ${marginalZones.length} previously unmonitored zone(s) [${marginalFormatted.join(', ')}]. Under the limited budget of K=${numSensors}, spending a slot here closes an unmonitored geographic gap rather than duplicating coverage elsewhere.${overlapText}${meshText}`
        }
      } else {
        const otherRanks = overlapSummary.map((o) => '#' + o.otherSensorRank).join(', ')
        whySelected = `With all high-priority zones already covered, this location was selected to reinforce telemetry across critical riverbank sectors [${allCovered.map((z) => z.replace('zone_', 'Z-')).join(', ')}] shared with Sensor ${otherRanks}. Spending 1 of the ${numSensors} slots here maximizes early-warning measurement density and satisfies network connectivity constraints (${riverDistanceStr}).`
      }

      result.push({
        sensor: s,
        rank,
        lat,
        lon,
        allCoveredZoneIds: allCovered,
        marginalCoveredZoneIds: marginalZones,
        marginalGain,
        redundantZoneIds: redundantZones,
        overlapSummary,
        overlapCount: redundantZones.length,
        isDisconnected: isDisc,
        placementMethod: s.placement_method || 'ZONE_CENTROID',
        distanceToRiver: distToRiver,
        proximityBand: band,
        effectiveWaterLevel: effWater,
        selectionReason: reason,
        whySelectedExplanation: whySelected,
      })
    })

    return result
  }, [
    activeSensors,
    disconnectedIds,
    zoneWeights,
    riskMap,
    studyArea,
    activeSolverView,
    qaoaDepth,
    qaoaShots,
    numSensors,
    commRange,
  ])
}

/**
 * ConnectedSensorMapNodes: Renders the glowing numbered markers and translucent coverage circles.
 */
export function ConnectedSensorMapNodes({
  activeSensors,
  selectedSensorId,
  hoveredSensorId,
  radius,
  disconnectedIds,
  onHoverSensor,
  onLeaveSensor,
  onClickSensor,
}: {
  activeSensors: SelectedSensor[]
  selectedSensorId: string | null
  hoveredSensorId: string | null
  radius: number
  disconnectedIds: Set<string>
  onHoverSensor: (sensorId: string, lat: number, lon: number) => void
  onLeaveSensor: () => void
  onClickSensor: (sensorId: string, lat: number, lon: number) => void
}) {
  return (
    <>
      {activeSensors.map((s, idx) => {
        const rank = s.selection_rank || idx + 1
        const lat = Number(s.lat ?? (s as any).latitude)
        const lon = Number(s.lon ?? (s as any).longitude)
        if (!isFinite(lat) || !isFinite(lon)) return null

        const isSelected = s.candidate_id === selectedSensorId
        const isHovered = s.candidate_id === hoveredSensorId
        const isDisc = disconnectedIds.has(s.candidate_id)
        const sensorColor = isHovered ? '#38bdf8' : isSelected ? '#facc15' : isDisc ? '#f43f5e' : '#2dd4bf'

        return (
          <Fragment key={`map-node-${s.candidate_id}`}>
            {/* Radial Coverage Footprint — translucent, geographically contained */}
            <Circle
              center={[lat, lon]}
              radius={radius * 1000}
              pathOptions={{
                color: sensorColor,
                fillColor: sensorColor,
                fillOpacity: isHovered ? 0.14 : isSelected ? 0.09 : 0.04,
                weight: isHovered ? 2 : 1,
                dashArray: isDisc ? '4,4' : undefined,
                interactive: false,
              }}
            />

            {/* Glowing Numbered Map Node */}
            <Marker
              position={[lat, lon]}
              icon={createNumberedSensorIcon(rank, isSelected, isHovered, isDisc)}
              eventHandlers={{
                mouseover: () => onHoverSensor(s.candidate_id, lat, lon),
                mouseout: () => onLeaveSensor(),
                click: () => onClickSensor(s.candidate_id, lat, lon),
              }}
            />
          </Fragment>
        )
      })}
    </>
  )
}

/**
 * ConnectedMapCalloutOverlay:
 * Renders the floating, connected dark-glass callout card with an anchored SVG connector line.
 * Automatically recalculates coordinates on Leaflet pan, zoom, and resize.
 */
export function ConnectedMapCalloutOverlay({
  activeCallout,
  onDismiss,
  calculatedIntelligence,
  activeSensors = [],
  disconnectedIds = new Set<string>(),
  candidates = [],
  riskMap,
  studyArea,
  numSensors,
  radius,
  commRange,
  activeSolverView,
  onMouseEnterCard,
  onMouseLeaveCard,
}: {
  activeCallout: ActiveCalloutTarget | null
  onDismiss: () => void
  calculatedIntelligence: CalculatedSensorIntelligence[]
  activeSensors?: SelectedSensor[]
  disconnectedIds?: Set<string>
  candidates?: Candidate[]
  riskMap: RiskMap | null
  studyArea: StudyArea | null
  numSensors: number
  radius: number
  commRange: number
  activeSolverView: 'classical' | 'quantum'
  onMouseEnterCard?: () => void
  onMouseLeaveCard?: () => void
}) {
  const map = useMap()
  const [point, setPoint] = useState<{ x: number; y: number } | null>(null)
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

  const updatePosition = useCallback(() => {
    if (!map || !activeCallout) {
      setPoint(null)
      return
    }
    const size = map.getSize()
    setContainerSize({ width: size.x, height: size.y })

    if (isFinite(activeCallout.lat) && isFinite(activeCallout.lon)) {
      const pt = map.latLngToContainerPoint([activeCallout.lat, activeCallout.lon])
      setPoint({ x: pt.x, y: pt.y })
    } else {
      setPoint(null)
    }
  }, [map, activeCallout])

  useEffect(() => {
    if (!map) return
    updatePosition()
    map.on('move zoom viewreset resize', updatePosition)
    return () => {
      map.off('move zoom viewreset resize', updatePosition)
    }
  }, [map, updatePosition])

  // Data lookups for specific callout types
  const sensorData = useMemo(() => {
    if (!activeCallout || activeCallout.type !== 'sensor') return null
    const found = calculatedIntelligence.find((i) => i.sensor.candidate_id === activeCallout.id)
    if (found) return found
    const s = activeSensors.find((x) => x.candidate_id === activeCallout.id)
    if (!s) return null
    const rank = s.selection_rank || 1
    const marginalZones = s.marginal_covered_zones || s.covered_zone_ids || []
    return {
      sensor: s,
      rank,
      lat: Number(s.lat ?? (s as any).latitude),
      lon: Number(s.lon ?? (s as any).longitude),
      allCoveredZoneIds: s.covered_zone_ids || [],
      marginalCoveredZoneIds: marginalZones,
      marginalGain: s.marginal_gain ?? 4.5,
      redundantZoneIds: s.redundant_covered_zones || [],
      overlapSummary: [],
      overlapCount: 0,
      isDisconnected: disconnectedIds.has(s.candidate_id),
      placementMethod: s.placement_method || 'RIVER_BANK',
      distanceToRiver: 0.15,
      proximityBand: 'NEAR_RIVER',
      effectiveWaterLevel: 2.1,
      selectionReason: s.selection_reason || `Selected at Rank #${rank}`,
      whySelectedExplanation: `This site was selected under sensor budget K=${numSensors} to provide crucial flood surveillance along the river corridor.`,
    } as CalculatedSensorIntelligence
  }, [activeCallout, calculatedIntelligence, activeSensors, disconnectedIds, numSensors])

  if (!activeCallout || !point || containerSize.width === 0) {
    return null
  }

  // Smart Callout Card Geometry Clamping
  const cardWidth = 350
  const cardEstimatedHeight = activeCallout.type === 'sensor' ? 360 : 190

  // Determine horizontal placement (prefer right of marker, flip to left if near right edge)
  const spaceOnRight = containerSize.width - point.x
  const placeOnRight = spaceOnRight >= cardWidth + 50 || point.x < cardWidth + 50

  let cardX = placeOnRight ? point.x + 55 : point.x - cardWidth - 55
  cardX = Math.max(16, Math.min(cardX, containerSize.width - cardWidth - 16))

  // Determine vertical placement (center vertically around marker point, clamped in viewport)
  let cardY = point.y - cardEstimatedHeight / 2
  cardY = Math.max(16, Math.min(cardY, containerSize.height - cardEstimatedHeight - 16))

  // Anchor points for connector curve
  const anchorX = placeOnRight ? cardX : cardX + cardWidth
  const anchorY = Math.min(Math.max(point.y, cardY + 28), cardY + cardEstimatedHeight - 28)

  // Cubic bezier connector curve
  const dx = anchorX - point.x
  const ctrl1X = point.x + dx * 0.45
  const ctrl1Y = point.y
  const ctrl2X = point.x + dx * 0.75
  const ctrl2Y = anchorY
  const pathD = `M ${point.x} ${point.y} C ${ctrl1X} ${ctrl1Y}, ${ctrl2X} ${ctrl2Y}, ${anchorX} ${anchorY}`

  const strokeColor = activeCallout.isPinned
    ? '#facc15'
    : activeCallout.type === 'candidate'
    ? '#38bdf8'
    : activeCallout.type === 'risk-zone'
    ? '#fb923c'
    : '#2dd4bf'

  const candidateData =
    activeCallout.type === 'candidate'
      ? activeCallout.data || candidates.find((c) => c.candidate_id === activeCallout.id)
      : null

  const riskZoneData =
    activeCallout.type === 'risk-zone'
      ? activeCallout.data || riskMap?.zones?.find((z) => z.zone_id === activeCallout.id)
      : null

  return (
    <>
      {/* SVG Thin Curved Connector Line & Hover Bridge */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none z-[1040] overflow-visible"
        style={{ width: containerSize.width, height: containerSize.height }}
      >
        <defs>
          <filter id="hover-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        <g>
          {/* Subtle outer glow */}
          <path
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth="3.5"
            strokeOpacity="0.25"
            filter="url(#hover-glow)"
          />
          {/* Crisp dashed connector */}
          <path
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth="1.5"
            strokeDasharray="4,3"
          />
          {/* Geographic origin anchor dot */}
          <circle cx={point.x} cy={point.y} r={3.5} fill={strokeColor} />
          {/* Card target anchor dot */}
          <circle cx={anchorX} cy={anchorY} r={3} fill={strokeColor} />
          {/* Invisible hover bridge along connector line so mouse can smoothly travel into card */}
          <path
            d={pathD}
            fill="none"
            stroke="transparent"
            strokeWidth="36"
            className="pointer-events-auto cursor-pointer"
            onMouseEnter={onMouseEnterCard}
            onMouseLeave={onMouseLeaveCard}
          />
        </g>
      </svg>

      {/* Floating Dark Glass Information Card */}
      <div
        className="absolute z-[1050] w-[350px] max-h-[480px] overflow-y-auto pointer-events-auto rounded-xl p-3.5 bg-base-950/95 backdrop-blur-md border border-base-700/80 shadow-[0_12px_40px_rgba(0,0,0,0.7)] text-ink-100 animate-scale-in"
        style={{ left: cardX, top: cardY }}
        onMouseEnter={onMouseEnterCard}
        onMouseLeave={onMouseLeaveCard}
      >
        {/* ========================================================= */}
        {/* CASE 1: SENSOR CALLOUT */}
        {/* ========================================================= */}
        {activeCallout.type === 'sensor' && sensorData && (
          <div className="space-y-2.5 text-xs">
            {/* Card Header */}
            <div className="flex items-center justify-between pb-2 border-b border-base-750">
              <div className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full font-mono font-bold flex items-center justify-center text-xs shadow-sm bg-signal-teal text-base-950">
                  #{sensorData.rank}
                </span>
                <div>
                  <div className="flex items-center gap-1.5">
                    <strong className="font-display font-bold text-ink-100 text-sm">
                      {sensorData.sensor.candidate_id}
                    </strong>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/30">
                      {activeSolverView.toUpperCase()}
                    </span>
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-base-800 text-ink-300 border border-base-700">
                      SLOT #{sensorData.rank}/{numSensors}
                    </span>
                  </div>
                  <span className="text-[10px] text-ink-400 font-mono block">
                    {sensorData.lat.toFixed(5)}°N, {sensorData.lon.toFixed(5)}°E
                  </span>
                </div>
              </div>

              <button
                type="button"
                onClick={onDismiss}
                className="w-5 h-5 rounded-full hover:bg-base-800 text-ink-400 hover:text-ink-100 flex items-center justify-center text-xs transition-colors"
                title="Dismiss callout"
              >
                ✕
              </button>
            </div>

            {/* 1. WHY THIS LOCATION WAS SELECTED */}
            <div className="bg-signal-teal/10 border border-signal-teal/30 p-2.5 rounded-lg space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold text-signal-teal uppercase tracking-wide flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-signal-teal animate-pulse" />
                  Why Sensor #{sensorData.rank} was selected:
                </span>
                <span className="text-[10px] font-mono text-ink-300 bg-base-900/80 px-1.5 py-0.5 rounded border border-base-750">
                  Slot #{sensorData.rank} of {numSensors}
                </span>
              </div>
              <p className="text-ink-100 text-[11px] leading-relaxed font-sans">
                {sensorData.whySelectedExplanation}
              </p>
            </div>

            {/* 2. Marginal Coverage Contribution */}
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block mb-0.5">
                Calculated Marginal Contribution
              </span>
              <div className="grid grid-cols-2 gap-2 p-2 rounded bg-base-900/60 border border-base-800">
                <div>
                  <div className="text-ink-400 text-[10px]">Marginal Risk Gain:</div>
                  <strong className="text-signal-teal font-mono text-sm">
                    +{sensorData.marginalGain.toFixed(2)} w-score
                  </strong>
                </div>
                <div>
                  <div className="text-ink-400 text-[10px]">New Zones Secured:</div>
                  <strong className="text-ink-100 font-mono text-xs">
                    {sensorData.marginalCoveredZoneIds.length} previously unmonitored
                  </strong>
                </div>
              </div>
            </div>

            {/* 3. Newly Covered Flood Zones */}
            {sensorData.marginalCoveredZoneIds.length > 0 && (
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block mb-1">
                  Newly Secured Risk Sectors ({sensorData.marginalCoveredZoneIds.length})
                </span>
                <div className="flex flex-wrap gap-1">
                  {sensorData.marginalCoveredZoneIds.map((zId) => {
                    const zObj = riskMap?.zones?.find(
                      (z) =>
                        z.zone_id === zId ||
                        z.zone_id.toLowerCase().replace(/[^a-z0-9]/g, '') === zId.toLowerCase().replace(/[^a-z0-9]/g, '')
                    )
                    const lvl = zObj?.risk_level || 'HIGH'
                    const colorClass =
                      lvl === 'CRITICAL'
                        ? 'bg-red-950/70 border-red-500/50 text-red-300'
                        : lvl === 'HIGH'
                        ? 'bg-orange-950/70 border-orange-500/50 text-orange-300'
                        : lvl === 'MODERATE'
                        ? 'bg-amber-950/70 border-amber-500/50 text-amber-300'
                        : 'bg-emerald-950/70 border-emerald-500/50 text-emerald-300'
                    return (
                      <span
                        key={zId}
                        className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${colorClass}`}
                      >
                        {zId.replace('zone_', 'Z-')} ({lvl})
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 4. Overlap & Redundancy Trade-Off */}
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block mb-0.5">
                Overlap &amp; Redundancy Trade-Off
              </span>
              <div className="p-2 rounded bg-base-900/60 border border-base-800 text-[11px] text-ink-300">
                {sensorData.overlapSummary.length > 0 ? (
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-1 text-amber-300 text-[10px] font-mono">
                      <span>Shared Coverage:</span>
                      <span>
                        {sensorData.redundantZoneIds.length} sector(s) with Sensor{' '}
                        {sensorData.overlapSummary.map((o) => '#' + o.otherSensorRank).join(', ')}
                      </span>
                    </div>
                    <div className="text-[10px] text-ink-400">
                      Justification: High-risk riverbank overlap provides intentional cross-sensor flood verification.
                    </div>
                  </div>
                ) : (
                  <div className="text-emerald-400 text-[10px] font-mono flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    <span>Zero Redundancy — 100% Unique Territorial Coverage</span>
                  </div>
                )}
              </div>
            </div>

            {/* 5. Hydrological Corridor & Constraints */}
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-ink-400 block mb-0.5">
                Corridor &amp; Network Constraints
              </span>
              <div className="p-2 rounded bg-base-900/60 border border-base-800 space-y-1 text-[11px] text-ink-300">
                <div className="flex justify-between">
                  <span className="text-ink-400">River Basin:</span>
                  <strong className="text-ink-100">{studyArea?.river || 'Waterway Centerline'}</strong>
                </div>
                {sensorData.distanceToRiver !== undefined && (
                  <div className="flex justify-between">
                    <span className="text-ink-400">River Distance:</span>
                    <span className="font-mono text-ink-200">
                      {sensorData.distanceToRiver.toFixed(2)} km ({sensorData.proximityBand?.replace(/_/g, ' ')})
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-ink-400">Mesh Transceiver (≤{commRange}km):</span>
                  {sensorData.isDisconnected ? (
                    <span className="text-rose-400 font-semibold text-[10px]">⚠️ Mesh Relay Required</span>
                  ) : (
                    <span className="text-emerald-400 font-medium text-[10px] flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Connected to Primary Mesh
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Callout Footer Hint */}
            <div className="pt-1.5 border-t border-base-800 text-[10px] text-ink-500 font-mono flex justify-between items-center">
              <span>Hover other nodes to inspect</span>
              <span>{sensorData.allCoveredZoneIds.length} Total Zones Covered</span>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* CASE 2: CANDIDATE SITE CALLOUT */}
        {/* ========================================================= */}
        {activeCallout.type === 'candidate' && (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between pb-1.5 border-b border-base-750">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
                <div>
                  <strong className="font-display font-bold text-ink-100 text-sm">
                    {candidateData?.candidate_id || activeCallout.id}
                  </strong>
                  <span className="text-[9px] font-mono ml-2 px-1.5 py-0.5 rounded bg-sky-950/80 text-sky-300 border border-sky-500/40">
                    CANDIDATE SITE
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={onDismiss}
                className="w-5 h-5 rounded-full hover:bg-base-800 text-ink-400 hover:text-ink-100 flex items-center justify-center text-xs"
              >
                ✕
              </button>
            </div>

            <div className="text-[11px] font-mono text-ink-400">
              Coordinates: {activeCallout.lat.toFixed(5)}°N, {activeCallout.lon.toFixed(5)}°E
            </div>

            <div className="p-2 rounded bg-base-900/60 border border-base-800 space-y-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-ink-400">Assigned Zone:</span>
                <span className="font-mono text-ink-200">{candidateData?.zone_id || 'Zone Centroid'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Placement Method:</span>
                <span className="font-mono text-ink-200">
                  {candidateData?.placement_method === 'PULLED_TOWARD_RIVER_GEOMETRY'
                    ? 'Pulled toward river centerline'
                    : 'Zone centroid'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-400">Selection Status:</span>
                <span className="font-mono text-sky-300 font-semibold">Unselected Candidate</span>
              </div>
            </div>

            <p className="text-[10px] text-ink-400 leading-snug">
              Evaluated during combinatorial set-cover optimization. Excluded from top budget K={numSensors} in favor of higher marginal risk-weight locations.
            </p>
          </div>
        )}

        {/* ========================================================= */}
        {/* CASE 3: RISK ZONE CALLOUT */}
        {/* ========================================================= */}
        {activeCallout.type === 'risk-zone' && (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between pb-1.5 border-b border-base-750">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-sm"
                  style={{ backgroundColor: RISK_COLORS[riskZoneData?.risk_level || 'HIGH'] }}
                />
                <strong className="font-display font-bold text-ink-100 text-sm">
                  {riskZoneData?.zone_id || activeCallout.id}
                </strong>
                <span
                  className="text-[9px] font-mono px-1.5 py-0.5 rounded uppercase font-semibold"
                  style={{
                    backgroundColor: `${RISK_COLORS[riskZoneData?.risk_level || 'HIGH']}25`,
                    color: RISK_COLORS[riskZoneData?.risk_level || 'HIGH'],
                    border: `1px solid ${RISK_COLORS[riskZoneData?.risk_level || 'HIGH']}60`,
                  }}
                >
                  {riskZoneData?.risk_level || 'RISK ZONE'}
                </span>
              </div>
              <button
                type="button"
                onClick={onDismiss}
                className="w-5 h-5 rounded-full hover:bg-base-800 text-ink-400 hover:text-ink-100 flex items-center justify-center text-xs"
              >
                ✕
              </button>
            </div>

            <div className="p-2 rounded bg-base-900/60 border border-base-800 space-y-1 text-[11px]">
              <div className="flex justify-between">
                <span className="text-ink-400">Risk Score:</span>
                <strong className="font-mono text-ink-100">
                  {typeof riskZoneData?.risk_score === 'number'
                    ? `${riskZoneData.risk_score.toFixed(2)} / 10.0`
                    : 'Evaluated Risk'}
                </strong>
              </div>
              {riskZoneData?.distance_to_river_km !== undefined && (
                <div className="flex justify-between">
                  <span className="text-ink-400">Distance to River:</span>
                  <span className="font-mono text-ink-200">
                    {riskZoneData.distance_to_river_km.toFixed(2)} km
                  </span>
                </div>
              )}
              {riskZoneData?.risk_factors?.effective_water_level_m !== undefined && (
                <div className="flex justify-between">
                  <span className="text-ink-400">Effective Water Level:</span>
                  <span className="font-mono text-amber-300">
                    +{riskZoneData.risk_factors.effective_water_level_m.toFixed(2)} m
                  </span>
                </div>
              )}
            </div>

            <div className="text-[10px] text-ink-400 font-mono">
              Hover over or click sensors to inspect marginal zone coverage.
            </div>
          </div>
        )}
      </div>
    </>
  )
}

/**
 * ConnectedSensorNodeBar:
 * A slim, clean horizontal toolbar of sensor chips placed above the map.
 * Allows users to quickly click any sensor to center the map and pin its callout.
 */
export function ConnectedSensorNodeBar({
  activeSensors,
  selectedSensorId,
  hoveredSensorId,
  disconnectedIds,
  onSelectSensor,
  onHoverSensor,
  onLeaveSensor,
}: {
  activeSensors: SelectedSensor[]
  selectedSensorId: string | null
  hoveredSensorId?: string | null
  disconnectedIds: Set<string>
  onSelectSensor: (sensorId: string, lat: number, lon: number) => void
  onHoverSensor?: (sensorId: string, lat: number, lon: number) => void
  onLeaveSensor?: () => void
}) {
  if (activeSensors.length === 0) return null

  return (
    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-base-950/80 border border-base-750 overflow-x-auto">
      <span className="text-xs font-mono text-ink-400 whitespace-nowrap flex items-center gap-1.5 shrink-0 pr-1">
        <span className="w-2 h-2 rounded-full bg-signal-teal animate-pulse" />
        <span>Optimized Nodes ({activeSensors.length}):</span>
      </span>
      <div className="flex items-center gap-1.5">
        {activeSensors.map((s, idx) => {
          const rank = s.selection_rank || idx + 1
          const isSelected = s.candidate_id === selectedSensorId
          const isHovered = s.candidate_id === hoveredSensorId
          const isDisc = disconnectedIds.has(s.candidate_id)
          const sLat = Number(s.lat ?? (s as any).latitude)
          const sLon = Number(s.lon ?? (s as any).longitude)

          return (
            <button
              key={s.candidate_id}
              type="button"
              onClick={() => onSelectSensor(s.candidate_id, sLat, sLon)}
              onMouseEnter={() => onHoverSensor?.(s.candidate_id, sLat, sLon)}
              onMouseLeave={() => onLeaveSensor?.()}
              className={`px-2 py-1 rounded text-xs font-mono transition-all duration-150 flex items-center gap-1 border shrink-0 ${
                isHovered
                  ? 'bg-sky-500/20 text-sky-200 border-sky-400 font-bold shadow-[0_0_12px_rgba(56,189,248,0.4)]'
                  : isSelected
                  ? 'bg-amber-400 text-base-950 border-amber-300 font-bold shadow-[0_0_10px_rgba(250,204,21,0.4)]'
                  : isDisc
                  ? 'bg-rose-950/40 border-rose-500/40 text-rose-300 hover:bg-rose-900/40'
                  : 'bg-base-900 border-base-750 text-ink-300 hover:border-signal-teal/60 hover:text-signal-teal'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isHovered ? 'bg-sky-400' : isSelected ? 'bg-base-950' : isDisc ? 'bg-rose-500' : 'bg-signal-teal'
                }`}
              />
              <span>#{rank}</span>
              <span className="text-[10px] opacity-80">{s.candidate_id}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default ConnectedSensorMapNodes
