import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError } from '../services/api'
import type {
  SafeLocationEvaluationResponse,
  SafeLocation,
  RiskMap,
  ShelterRequest,
  ShelterRequestUrgency,
  StudyArea,
  EvacuationRouteResponse,
  ShelterPortfolioQuantumResponse,
} from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { SafeLocationMarkersLayer, EvacuationRouteLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

const RESOURCE_TYPES = [
  'Clean Drinking Water (L)',
  'Emergency Food Rations (Packs)',
  'Medical First-Aid Kits',
  'Blankets & Bedding Sets',
  'Mobile Power Generators',
]

const URGENCY_STYLES: Record<string, string> = {
  LOW: 'text-emerald-400 bg-emerald-950/60 border-emerald-500/30',
  MODERATE: 'text-sky-400 bg-sky-950/60 border-sky-500/30',
  HIGH: 'text-amber-400 bg-amber-950/60 border-amber-500/30',
  CRITICAL: 'text-red-400 bg-red-950/60 border-red-500/30 animate-pulse',
}

const STATUS_STYLES: Record<string, string> = {
  PENDING: 'text-amber-400 bg-amber-950/40 border-amber-500/30',
  PARTIALLY_ALLOCATED: 'text-sky-400 bg-sky-950/40 border-sky-500/30',
  ALLOCATED: 'text-purple-400 bg-purple-950/40 border-purple-500/30',
  PARTIALLY_FULFILLED: 'text-teal-400 bg-teal-950/40 border-teal-500/30',
  FULFILLED: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30',
  CANCELLED: 'text-ink-500 bg-base-800 border-base-700',
}

export default function SafeShelters() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<SafeLocationEvaluationResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [studyArea, setStudyArea] = useState<StudyArea | null>(null)
  const [loading, setLoading] = useState(true)
  const [evaluating, setEvaluating] = useState(false)

  // Active view tab: "OPERATIONAL" vs "PROPOSED"
  const [activeTab, setActiveTab] = useState<'OPERATIONAL' | 'PROPOSED'>('OPERATIONAL')
  const [selectedLoc, setSelectedLoc] = useState<SafeLocation | null>(null)

  // Shelter Operator Requests State
  const [requests, setRequests] = useState<ShelterRequest[]>([])
  const [submittingReq, setSubmittingReq] = useState(false)
  const [formSuccess, setFormSuccess] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  // Request Form fields
  const [formShelterId, setFormShelterId] = useState('')
  const [formShelterName, setFormShelterName] = useState('')
  const [formResourceType, setFormResourceType] = useState(RESOURCE_TYPES[0])
  const [formQuantity, setFormQuantity] = useState(500)
  const [formUrgency, setFormUrgency] = useState<ShelterRequestUrgency>('HIGH')
  const [formNotes, setFormNotes] = useState('')

  // MCDA Weights
  const [weightElev, setWeightElev] = useState(0.25)
  const [weightRisk, setWeightRisk] = useState(0.35)
  const [weightDist, setWeightDist] = useState(0.20)
  const [weightAccess, setWeightAccess] = useState(0.20)

  // Evacuation route state
  const [evacRoute, setEvacRoute] = useState<EvacuationRouteResponse | null>(null)
  const [routeLoading, setRouteLoading] = useState(false)

  // Quantum Shelter Portfolio Optimization state
  const [portfolioResult, setPortfolioResult] = useState<ShelterPortfolioQuantumResponse | null>(null)
  const [portfolioBudget, setPortfolioBudget] = useState(3)
  const [portfolioMinDist, setPortfolioMinDist] = useState(1.5)
  const [portfolioLoading, setPortfolioLoading] = useState(false)
  const [portfolioError, setPortfolioError] = useState<string | null>(null)

  const handleOptimizePortfolio = async () => {
    setPortfolioLoading(true)
    setPortfolioError(null)
    try {
      const res = await api.optimizeShelterPortfolio({
        budget: portfolioBudget,
        min_separation_km: portfolioMinDist,
        study_area: studyArea || undefined,
      })
      setPortfolioResult(res)
    } catch (err: any) {
      setPortfolioError(err?.message || 'Failed to optimize shelter portfolio.')
    } finally {
      setPortfolioLoading(false)
    }
  }

  const loadRequests = async () => {
    try {
      const res = await api.listShelterRequests()
      setRequests(res.requests || [])
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    Promise.all([
      api.currentArea().catch(() => null),
      api.evaluateSafeLocations({
        weight_elevation: weightElev,
        weight_risk: weightRisk,
        weight_distance: weightDist,
        weight_accessibility: weightAccess,
      }).catch(() => null),
      api.riskZones().catch(() => null),
      api.listShelterRequests().catch(() => ({ requests: [] })),
    ])
      .then(([areaRes, evalRes, rm, reqs]) => {
        const activeArea = areaRes?.study_area || null
        if (activeArea) setStudyArea(activeArea)
        if (rm) setRiskMap(rm)
        if (reqs?.requests) setRequests(reqs.requests)

        if (evalRes) {
          setData(evalRes)
          const operational = evalRes.operational_shelters || []
          const proposed = evalRes.proposed_candidate_sites || []

          if (operational.length > 0) {
            setActiveTab('OPERATIONAL')
            setSelectedLoc(operational[0])
            setFormShelterId(operational[0].id)
            setFormShelterName(operational[0].name)
          } else {
            setActiveTab('PROPOSED')
            if (proposed.length > 0) {
              setSelectedLoc(proposed[0])
            }
          }
        }
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
        study_area: studyArea || undefined,
      })
      setData(res)
      const operational = res.operational_shelters || []
      const proposed = res.proposed_candidate_sites || []

      if (activeTab === 'OPERATIONAL' && operational.length > 0) {
        setSelectedLoc(operational[0])
        setFormShelterId(operational[0].id)
        setFormShelterName(operational[0].name)
      } else if (proposed.length > 0) {
        setSelectedLoc(proposed[0])
      }
    } catch (err: any) {
      console.error('Failed to evaluate safe locations:', err)
    } finally {
      setEvaluating(false)
    }
  }

  const handleSelectShelter = (loc: SafeLocation) => {
    setSelectedLoc(loc)
    const isOp = loc.shelter_type === 'OPERATIONAL_SHELTER' || loc.is_operational === true
    if (isOp) {
      setFormShelterId(loc.id)
      setFormShelterName(loc.name)
      setFormError(null)
    } else {
      setFormShelterId(loc.id)
      setFormShelterName(loc.name)
    }
  }

  // Handle plan evacuation route to selected location
  const handlePlanEvacuation = async (destLoc: SafeLocation) => {
    setRouteLoading(true)
    try {
      // Default origin is a high-risk riparian zone centroid near Prakasam Barrage
      const originLat = 16.5061
      const originLon = 80.605
      const res = await api.planEvacuationRoute({
        origin_lat: originLat,
        origin_lon: originLon,
        dest_lat: destLoc.lat,
        dest_lon: destLoc.lon,
        origin_name: 'Krishna Riverfront Evacuation Zone',
        dest_name: destLoc.name,
      })
      setEvacRoute(res)
    } catch (err: any) {
      console.error('Failed to compute evacuation route:', err)
    } finally {
      setRouteLoading(false)
    }
  }

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmittingReq(true)
    setFormSuccess(null)
    setFormError(null)

    const isOp = selectedLoc?.shelter_type === 'OPERATIONAL_SHELTER' || selectedLoc?.is_operational === true
    if (!isOp) {
      setFormError(
        'Shelter resource requests can only be dispatched to verified operational facilities (e.g. FAC-001..FAC-004). Proposed candidate sites are analytical suggestions, not functioning operational shelters.'
      )
      setSubmittingReq(false)
      return
    }

    if (!formShelterName.trim()) {
      setFormError('Please select a verified operational shelter facility.')
      setSubmittingReq(false)
      return
    }

    if (formQuantity <= 0) {
      setFormError('Requested quantity must be greater than zero.')
      setSubmittingReq(false)
      return
    }

    try {
      const res = await api.createShelterRequest({
        shelter_id: formShelterId,
        shelter_name: formShelterName,
        resource_type: formResourceType,
        requested_quantity: formQuantity,
        urgency: formUrgency,
        notes: formNotes,
      })
      if (res.status === 'SUCCESS') {
        setFormSuccess(`Request ${res.request.id} successfully lodged for ${formShelterName}! Available in Resource Planning.`)
        setFormNotes('')
        loadRequests()
      }
    } catch (err: any) {
      setFormError(err?.message || 'Failed to submit shelter resource request.')
    } finally {
      setSubmittingReq(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading verified shelters & MCDA suitability analysis..." />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = layers?.study_area?.center
    ? [Number(layers.study_area.center.lat), Number(layers.study_area.center.lon)]
    : [16.5061, 80.605]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))

  const operationalShelters = data?.operational_shelters || []
  const proposedCandidateSites = data?.proposed_candidate_sites || data?.locations || []
  const displayedLocations = activeTab === 'OPERATIONAL' ? operationalShelters : proposedCandidateSites
  const isSelectedOperational = selectedLoc?.shelter_type === 'OPERATIONAL_SHELTER' || selectedLoc?.is_operational === true

  return (
    <div className="flex flex-col gap-8 page-enter">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-emerald-400 mb-1">
          <span>SECTION 04</span>
          <span>/</span>
          <span>SHELTER ASSESSMENT &amp; OPERATOR DISPATCH</span>
        </div>
        <h1 className="font-display text-2xl sm:text-3xl text-ink-100 font-bold tracking-tight">
          Safe Shelters &amp; Shelter Requests
        </h1>
        <p className="text-ink-400 text-sm mt-1 max-w-3xl leading-relaxed">
          Identifies verified operational emergency shelters when supported by municipal data.
          When no existing shelters exist in an area, multi-criteria decision analysis (MCDA) recommends candidate sites suitable for establishing emergency relief facilities.
        </p>

        {studyArea && (
          <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-900 border border-base-700 text-xs text-ink-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Active Study Area:</span>
            <strong className="text-ink-100 font-semibold">{studyArea.name}</strong>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-base-800 text-ink-400 border border-base-700">
              {operationalShelters.length > 0 ? `${operationalShelters.length} Verified Shelters Available` : 'No Operational Shelters in Database'}
            </span>
          </div>
        )}
      </div>

      {/* Strict Operational vs Proposed Distinction Banner */}
      <div className="panel p-4 bg-base-900/90 border-emerald-500/30 flex items-start gap-3 rounded-xl">
        <div className="p-2 rounded bg-emerald-500/10 text-emerald-400 shrink-0 mt-0.5">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
        <div className="text-xs text-ink-300 leading-relaxed">
          <strong className="text-emerald-400 font-semibold">Strict Verification &amp; Classification Standard:</strong>
          {' '}The system strictly differentiates verified operational relief facilities from analytical recommendations.
          <span className="text-ink-100 font-medium"> Verified operational shelters</span> possess documented structural capacity and can receive emergency supplies.
          <span className="text-amber-300 font-medium"> Proposed candidate sites</span> are analytical suggestions ranked by terrain elevation and road access where authorities could establish new shelters during catastrophic events.
        </div>
      </div>

      {/* Main Grid: Interactive Map & Shelters Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Interactive Map with Evacuation Layer */}
        <div className="lg:col-span-2 panel p-3 sm:p-5 flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3">
              <span className="eyebrow">Spatial Assessment</span>
              <div className="flex flex-col sm:flex-row rounded-lg bg-base-900 p-0.5 border border-base-750 gap-0.5">
                <button
                  onClick={() => {
                    setActiveTab('OPERATIONAL')
                    if (operationalShelters.length > 0) {
                      handleSelectShelter(operationalShelters[0])
                    }
                  }}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors min-h-[38px] sm:min-h-0 text-center flex items-center justify-center ${
                    activeTab === 'OPERATIONAL'
                      ? 'bg-emerald-500 text-base-950 font-bold shadow-sm'
                      : 'text-ink-400 hover:text-ink-200'
                  }`}
                >
                  Operational Shelters ({operationalShelters.length})
                </button>
                <button
                  onClick={() => {
                    setActiveTab('PROPOSED')
                    if (proposedCandidateSites.length > 0) {
                      handleSelectShelter(proposedCandidateSites[0])
                    }
                  }}
                  className={`px-3 py-1.5 rounded text-xs font-mono font-medium transition-colors min-h-[38px] sm:min-h-0 text-center flex items-center justify-center ${
                    activeTab === 'PROPOSED'
                      ? 'bg-signal-cyan text-base-950 font-bold shadow-sm'
                      : 'text-ink-400 hover:text-ink-200'
                  }`}
                >
                  Proposed Candidate Sites ({proposedCandidateSites.length})
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400" />
              <span className="text-ink-400">Operational</span>
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-sky-400 ml-2" />
              <span className="text-ink-400">Proposed Site</span>
            </div>
          </div>

          <div className="rounded-lg overflow-hidden border border-base-700 h-[340px] sm:h-[420px] lg:h-[480px]">
            <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="100%">
              <LayersControl position="topright">
                <LayersOverlay name="Study Area Boundary" checked>
                  <StudyAreaBoundaryLayer boundary={layers.boundary} />
                </LayersOverlay>
                <LayersOverlay name={layers.study_area?.river || 'River Centerline'} checked>
                  <RiverLayer river={layers.river} />
                </LayersOverlay>
                <LayersOverlay name="Flood Risk Zones" checked>
                  <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
                </LayersOverlay>
                <LayersOverlay name="All Shelters &amp; Candidate Sites" checked>
                  <SafeLocationMarkersLayer
                    locations={data?.locations || []}
                    onLocationClick={handleSelectShelter}
                  />
                </LayersOverlay>
                {evacRoute && (
                  <LayersOverlay name="Evacuation Route (Dijkstra)" checked>
                    <EvacuationRouteLayer
                      primaryRoute={evacRoute.primary_route}
                      alternativeRoute={evacRoute.alternative_route}
                      origin={evacRoute.origin}
                      destination={evacRoute.destination}
                    />
                  </LayersOverlay>
                )}
              </LayersControl>
            </GeoMap>
          </div>

          {evacRoute && evacRoute.primary_route && (
            <div className="p-3 bg-base-850 rounded-lg border border-base-700 flex flex-col sm:flex-row sm:items-center justify-between text-xs text-ink-300 gap-2">
              <div className="flex items-center gap-2">
                <span className="text-signal-teal font-mono font-bold">ROUTE PLANNED:</span>
                <span>To <strong className="text-ink-100">{selectedLoc?.name}</strong></span>
                <span className="text-ink-500 font-mono">({evacRoute.primary_route.total_distance_km} km)</span>
              </div>
              <div className="flex items-center gap-3 text-xs font-mono">
                <span>Risk Score: <strong className="text-signal-cyan">{evacRoute.primary_route.estimated_route_risk_score}</strong></span>
                <button
                  onClick={() => setEvacRoute(null)}
                  className="text-ink-400 hover:text-ink-100 underline ml-2"
                >
                  Clear Route
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Col: Shelters List & MCDA Tuning */}
        <div className="panel p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-base-700/60 pb-3">
              <h3 className="font-display font-semibold text-base text-ink-100">
                {activeTab === 'OPERATIONAL' ? 'Operational Relief Facilities' : 'Candidate Construction Sites'}
              </h3>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                activeTab === 'OPERATIONAL'
                  ? 'bg-emerald-950 text-emerald-400 border-emerald-500/30'
                  : 'bg-sky-950 text-sky-400 border-sky-500/30'
              }`}>
                {activeTab === 'OPERATIONAL' ? 'VERIFIED DATA' : 'MCDA RANKED'}
              </span>
            </div>

            {/* Empty state for operational shelters */}
            {activeTab === 'OPERATIONAL' && operationalShelters.length === 0 ? (
              <div className="p-5 text-center bg-base-850/60 rounded-lg border border-base-750 mt-4">
                <div className="w-8 h-8 mx-auto rounded-full bg-base-800 text-amber-400 flex items-center justify-center p-1.5">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h4 className="font-display text-xs font-semibold text-ink-100 mt-2">
                  No Existing Shelters in Current Dataset
                </h4>
                <p className="text-[11px] text-ink-400 mt-1 leading-relaxed">
                  No verified operational shelters exist for this study area. Click the &quot;Proposed Candidate Sites&quot; tab to inspect locations where emergency shelters could potentially be built.
                </p>
                <button
                  onClick={() => setActiveTab('PROPOSED')}
                  className="mt-3 px-3 py-1 rounded bg-signal-cyan/20 text-signal-cyan border border-signal-cyan/40 text-xs font-mono hover:bg-signal-cyan/30"
                >
                  View Proposed Candidate Sites →
                </button>
              </div>
            ) : activeTab === 'PROPOSED' && proposedCandidateSites.length === 0 ? (
              <div className="p-5 text-center bg-base-850/60 rounded-lg border border-base-750 mt-4">
                <div className="w-8 h-8 mx-auto rounded-full bg-base-800 text-amber-400 flex items-center justify-center p-1.5">
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <h4 className="font-display text-xs font-semibold text-ink-100 mt-2">
                  No Candidate Shelter Sites Available
                </h4>
                <p className="text-[11px] text-ink-400 mt-1 leading-relaxed">
                  Neither verified operational shelters nor sufficient geographic data (road network or elevation records) exist to calculate suitable candidate sites for this area.
                </p>
              </div>
            ) : (
              <div className="space-y-2 mt-4 max-h-[340px] overflow-y-auto pr-1">
                {displayedLocations.map((loc) => {
                  const isSelected = selectedLoc?.id === loc.id
                  const isOp = loc.shelter_type === 'OPERATIONAL_SHELTER' || loc.is_operational === true
                  return (
                    <button
                      key={loc.id}
                      onClick={() => handleSelectShelter(loc)}
                      className={`w-full text-left p-3 rounded-lg border transition-all duration-150 ${
                        isSelected
                          ? isOp
                            ? 'bg-base-750 border-emerald-400 text-ink-100 shadow-md ring-1 ring-emerald-400/40'
                            : 'bg-base-750 border-signal-cyan text-ink-100 shadow-md ring-1 ring-signal-cyan/40'
                          : 'bg-base-850 border-base-700/60 text-ink-300 hover:bg-base-800'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs text-ink-100 truncate pr-2">{loc.name}</span>
                        {isOp ? (
                          <span className="font-mono text-xs font-bold text-emerald-400 shrink-0">
                            {loc.capacity_estimate ? `${loc.capacity_estimate} cap` : 'OPERATIONAL'}
                          </span>
                        ) : (
                          <span className="font-mono text-xs font-bold text-signal-cyan shrink-0">
                            {loc.suitability_score?.toFixed(1) ?? '—'}/100
                          </span>
                        )}
                      </div>

                      <div className="text-[10px] text-ink-400 mt-1">
                        {isOp ? (
                          <span className="text-emerald-300 font-mono">Verified Relief Shelter · Active Facility</span>
                        ) : (
                          <span className="text-amber-400 font-mono">Proposed Candidate Site — Not an Existing Shelter</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-ink-500 font-mono mt-1.5 pt-1.5 border-t border-base-700/40">
                        <span>Elev: {loc.elevation_m?.toFixed(1)}m</span>
                        <span>River: {loc.distance_to_river_km?.toFixed(2)}km</span>
                        <span>Road: {loc.primary_road_access || 'Connected'}</span>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}

            {/* Selected Location Details Drawer */}
            {selectedLoc && (
              <div className="mt-4 p-3 rounded-lg bg-base-900 border border-base-750 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-ink-500 uppercase">Selected Entity Details</span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                    isSelectedOperational
                      ? 'bg-emerald-950 text-emerald-400 border-emerald-500/40'
                      : 'bg-amber-950 text-amber-400 border-amber-500/40'
                  }`}>
                    {isSelectedOperational ? 'Operational Shelter' : 'Proposed Construction Site'}
                  </span>
                </div>
                <div className="font-semibold text-sm text-ink-100 mt-1">{selectedLoc.name}</div>
                <p className="text-[11px] text-ink-400 mt-1 leading-snug">
                  {selectedLoc.explanation || 'Evaluated for topographic standoff and flood avoidance.'}
                </p>

                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => handlePlanEvacuation(selectedLoc)}
                    disabled={routeLoading}
                    className="flex-1 bg-base-800 hover:bg-base-750 text-signal-teal border border-base-700 text-xs font-medium py-1.5 px-2 rounded transition-colors"
                  >
                    {routeLoading ? 'Routing…' : 'Plan Evacuation Route'}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* MCDA Tuning Sliders */}
          <div className="mt-4 pt-4 border-t border-base-700/60">
            <span className="text-[10px] font-mono text-ink-400 uppercase tracking-wider block mb-2">
              MCDA Multi-Criteria Weights
            </span>
            <div className="grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <div className="flex justify-between text-ink-400 font-mono mb-0.5">
                  <span>Elevation:</span>
                  <span>{weightElev.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.1}
                  max={0.6}
                  step={0.05}
                  value={weightElev}
                  onChange={(e) => setWeightElev(Number(e.target.value))}
                  className="w-full accent-signal-cyan"
                />
              </div>

              <div>
                <div className="flex justify-between text-ink-400 font-mono mb-0.5">
                  <span>Flood Risk:</span>
                  <span>{weightRisk.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0.1}
                  max={0.6}
                  step={0.05}
                  value={weightRisk}
                  onChange={(e) => setWeightRisk(Number(e.target.value))}
                  className="w-full accent-signal-cyan"
                />
              </div>
            </div>

            <button
              onClick={handleEvaluate}
              disabled={evaluating}
              className="mt-3 w-full bg-base-800 hover:bg-base-750 text-ink-200 border border-base-700 text-xs font-medium py-2 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {evaluating ? 'Recalculating MCDA…' : 'Recalculate Suitability Scores'}
            </button>
          </div>
        </div>
      </div>

      {/* Hybrid Quantum Shelter Portfolio Optimizer (Milestone 4) */}
      <div className="panel p-6 border-signal-blueDim/40">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-base-750 pb-3 mb-4 gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-signal-blue" />
              <span className="eyebrow text-signal-blue">Combinatorial Portfolio Optimization</span>
            </div>
            <h3 className="font-display text-lg text-ink-100 font-semibold mt-0.5">
              Hybrid Quantum Shelter Portfolio Selection (QAOA)
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Formulated as an Ising/QUBO problem to select high-suitability proposed construction sites while penalizing spatial clustering. Verified operational shelters remain completely untouched.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-signal-blue border border-signal-blue/30 self-start sm:self-auto">
            QAOA QUBO SOLVER
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-400 uppercase block mb-1">
              Shelter Budget (k sites)
            </label>
            <input
              type="number"
              min={1}
              max={6}
              value={portfolioBudget}
              onChange={(e) => setPortfolioBudget(Math.max(1, Number(e.target.value)))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>

          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-400 uppercase block mb-1">
              Min Separation (km)
            </label>
            <input
              type="number"
              step={0.5}
              min={0.5}
              max={10.0}
              value={portfolioMinDist}
              onChange={(e) => setPortfolioMinDist(Math.max(0.5, Number(e.target.value)))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={handleOptimizePortfolio}
              disabled={portfolioLoading || proposedCandidateSites.length === 0}
              className="w-full bg-signal-blue/20 hover:bg-signal-blue/30 text-signal-blue border border-signal-blue/40 text-xs font-semibold py-2 px-4 rounded-lg transition-colors disabled:opacity-40 min-h-[44px] flex items-center justify-center"
            >
              {portfolioLoading ? 'Simulating QAOA Circuit…' : 'Run Quantum Portfolio Optimizer'}
            </button>
          </div>
        </div>

        {portfolioError && (
          <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 text-red-300 text-xs mb-4">
            {portfolioError}
          </div>
        )}

        {portfolioResult && (
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">QAOA Mean Suitability:</span>
                <strong className="text-signal-blue font-mono text-base">
                  {portfolioResult.mean_suitability_score.toFixed(1)}/100
                </strong>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Min Pairwise Dist:</span>
                <strong className="text-signal-teal font-mono text-base">
                  {portfolioResult.minimum_pairwise_distance_km.toFixed(2)} km
                </strong>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Classical Baseline:</span>
                <strong className="text-ink-200 font-mono text-base">
                  {portfolioResult.classical_baseline.mean_suitability.toFixed(1)}/100
                </strong>
                <span className="text-[10px] text-ink-500 block font-mono">
                  Min dist: {portfolioResult.classical_baseline.minimum_pairwise_distance_km.toFixed(2)} km
                </span>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Solver Runtime:</span>
                <strong className="text-ink-200 font-mono text-sm block">
                  Quantum: {portfolioResult.solver_metadata.execution_time_ms.toFixed(1)} ms
                </strong>
                <span className="text-[10px] text-ink-500 font-mono">
                  Classical: {portfolioResult.classical_baseline.execution_time_ms.toFixed(1)} ms
                </span>
              </div>
            </div>

            {/* Selected Shelters List */}
            <div className="p-4 bg-base-900/90 rounded-lg border border-base-750">
              <span className="text-[10px] font-mono text-signal-blue uppercase font-semibold block mb-2">
                QAOA Recommended Proposed Sites Portfolio ({portfolioResult.selected_shelters.length} selected)
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {portfolioResult.selected_shelters.map((s) => (
                  <div key={s.id} className="p-2.5 rounded bg-base-850 border border-base-700/70 text-xs">
                    <div className="font-semibold text-ink-100 truncate">{s.name}</div>
                    <div className="text-[10px] text-ink-400 font-mono mt-0.5">ID: {s.id}</div>
                    <div className="flex justify-between items-center text-[11px] font-mono mt-1 pt-1 border-t border-base-750 text-ink-300">
                      <span>Suitability: <strong className="text-signal-cyan">{s.suitability_score.toFixed(1)}</strong></span>
                      {s.elevation_m !== undefined && <span>{s.elevation_m.toFixed(1)}m elev</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Truthful Quantum Circuit Provenance Card */}
            <div className="p-3 rounded-lg bg-base-950 border border-base-800 text-[11px] font-mono text-ink-400 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-signal-blue font-bold">QAOA PROVENANCE:</span>
                <span>Backend: <strong className="text-ink-200">{portfolioResult.solver_metadata.backend}</strong></span>
                <span>• Qubits: <strong className="text-ink-200">{portfolioResult.solver_metadata.num_qubits}</strong></span>
                <span>• Depth: <strong className="text-ink-200">{portfolioResult.solver_metadata.circuit_depth}</strong></span>
                <span>• CNOTs: <strong className="text-ink-200">{portfolioResult.solver_metadata.cnot_count}</strong></span>
                <span>• Shots: <strong className="text-ink-200">{portfolioResult.solver_metadata.shots}</strong></span>
              </div>
              <span className="text-[10px] text-ink-500">
                Real statevector circuit simulation. Verified operational shelters protected from mutation.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Shelter Operator Request Submission Form */}
      <div className="panel p-6 border-base-700">
        <div className="border-b border-base-700/60 pb-3 mb-5 flex items-center justify-between">
          <div>
            <span className="eyebrow">Operator Portal</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Create Shelter Resource Request
            </h3>
            <p className="text-ink-400 text-xs mt-0.5">
              Authorized shelter operators can log operational supply needs. Requests automatically sync to Resource Planning &amp; Fulfillment.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-emerald-400 border border-base-700">
            OPERATIONAL SHELTERS ONLY
          </span>
        </div>

        {/* Form Validation Warning if targeting a proposed site */}
        {!isSelectedOperational && selectedLoc && (
          <div className="mb-4 p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 text-amber-300 text-xs flex items-center gap-2">
            <span>⚠️</span>
            <span>
              <strong>Proposed Candidate Site Selected:</strong> You cannot submit a resource request for <em className="font-semibold">{selectedLoc.name}</em> because it is an analytical candidate site, not a functioning operational shelter. Select a verified shelter above.
            </span>
          </div>
        )}

        <form onSubmit={handleCreateRequest} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono text-ink-300">Operational Shelter Facility</label>
            <select
              value={formShelterId}
              onChange={(e) => {
                const s = operationalShelters.find((o) => o.id === e.target.value)
                if (s) {
                  setFormShelterId(s.id)
                  setFormShelterName(s.name)
                  setSelectedLoc(s)
                }
              }}
              disabled={operationalShelters.length === 0}
              className="bg-base-900 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 focus:outline-none focus:border-emerald-400 disabled:opacity-40"
              required
            >
              {operationalShelters.length === 0 ? (
                <option value="">No operational shelters available</option>
              ) : (
                operationalShelters.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.id})
                  </option>
                ))
              )}
            </select>
            <span className="text-[10px] text-ink-500 font-mono">
              {operationalShelters.length > 0 ? `Selected ID: ${formShelterId}` : 'Dispatch unavailable'}
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono text-ink-300">Resource Required</label>
            <select
              value={formResourceType}
              onChange={(e) => setFormResourceType(e.target.value)}
              className="bg-base-900 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 focus:outline-none focus:border-emerald-400"
            >
              {RESOURCE_TYPES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <span className="text-[10px] text-ink-500 font-mono">Tracked commodity category</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono text-ink-300">Requested Quantity</label>
            <input
              type="number"
              min={1}
              max={50000}
              value={formQuantity}
              onChange={(e) => setFormQuantity(Number(e.target.value))}
              className="bg-base-900 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 focus:outline-none focus:border-emerald-400 font-mono"
              required
            />
            <span className="text-[10px] text-ink-500 font-mono">Units / Litres / Packs</span>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-mono text-ink-300">Urgency Level</label>
            <select
              value={formUrgency}
              onChange={(e) => setFormUrgency(e.target.value as ShelterRequestUrgency)}
              className="bg-base-900 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 focus:outline-none focus:border-emerald-400"
            >
              <option value="LOW">LOW</option>
              <option value="MODERATE">MODERATE</option>
              <option value="HIGH">HIGH</option>
              <option value="CRITICAL">CRITICAL</option>
            </select>
            <span className="text-[10px] text-ink-500 font-mono">Triage priority</span>
          </div>

          <div className="md:col-span-2 lg:col-span-3 flex flex-col gap-1.5">
            <label className="text-xs font-mono text-ink-300">Operational Notes &amp; Shelter Status</label>
            <input
              type="text"
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              placeholder="e.g. 320 flood evacuees arrived; drinking water stores depleted."
              className="bg-base-900 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 focus:outline-none focus:border-emerald-400"
            />
          </div>

          <div className="flex items-end">
            <button
              type="submit"
              disabled={submittingReq || operationalShelters.length === 0 || !isSelectedOperational}
              className="w-full bg-emerald-500 hover:bg-emerald-400 text-base-950 font-semibold py-2.5 px-4 rounded text-xs transition-colors shadow-sm disabled:opacity-40 min-h-[44px] flex items-center justify-center"
            >
              {submittingReq ? 'Submitting Request…' : 'Submit Resource Request'}
            </button>
          </div>
        </form>

        {formSuccess && (
          <div className="mt-4 p-3 rounded bg-emerald-950/40 border border-emerald-500/50 text-emerald-300 text-xs flex items-center gap-2">
            <span>✓</span>
            <span>{formSuccess}</span>
          </div>
        )}

        {formError && (
          <div className="mt-4 p-3 rounded bg-red-950/40 border border-red-500/50 text-red-300 text-xs flex items-center gap-2">
            <span>⚠️</span>
            <span>{formError}</span>
          </div>
        )}
      </div>

      {/* Active Shelter Requests & Status Log */}
      <div className="panel p-6 border-base-700">
        <div className="flex items-center justify-between border-b border-base-700/60 pb-3 mb-4">
          <div>
            <span className="eyebrow">Tracking Table</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Shelter Request Status &amp; Fulfillment Log
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Live status of requests dispatched to central warehouse logistics.
            </p>
          </div>
          <button
            onClick={loadRequests}
            className="text-xs font-mono text-ink-400 hover:text-signal-teal transition-colors underline"
          >
            Refresh Records
          </button>
        </div>

        <div className="responsive-table-container">
          <table className="w-full text-left text-xs text-ink-300 min-w-[700px]">
            <thead className="bg-base-800 font-mono text-[11px] text-ink-400 uppercase border-b border-base-700">
              <tr>
                <th className="py-2.5 px-3">Request ID</th>
                <th className="py-2.5 px-3">Shelter Facility</th>
                <th className="py-2.5 px-3">Resource Type</th>
                <th className="py-2.5 px-3">Requested</th>
                <th className="py-2.5 px-3">Allocated</th>
                <th className="py-2.5 px-3">Urgency</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-base-800">
              {requests.map((r) => (
                <tr key={r.id} className="hover:bg-base-800/40">
                  <td className="py-2.5 px-3 font-mono font-semibold text-ink-100">{r.id}</td>
                  <td className="py-2.5 px-3 font-medium text-ink-200">{r.shelter_name}</td>
                  <td className="py-2.5 px-3">{r.resource_type}</td>
                  <td className="py-2.5 px-3 font-mono font-bold text-ink-100">{r.requested_quantity.toLocaleString()}</td>
                  <td className="py-2.5 px-3 font-mono text-purple-300">{r.allocated_quantity.toLocaleString()}</td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${URGENCY_STYLES[r.urgency] || URGENCY_STYLES.MODERATE}`}>
                      {r.urgency}
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${STATUS_STYLES[r.status] || STATUS_STYLES.PENDING}`}>
                      {r.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-ink-400 truncate max-w-[200px]" title={r.notes || ''}>
                    {r.notes || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
