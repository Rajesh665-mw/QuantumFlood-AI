import { useEffect, useState, useRef, useCallback } from 'react'
import { useLocation } from 'react-router-dom'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError } from '../services/api'
import type { RiskMap as RiskMapType, StudyArea, LocationSearchResult } from '../types'
import RiskBadge from '../components/RiskBadge'
import RiskLegend from '../components/map/RiskLegend'
import GeoMap, { LayersControl, LayersOverlay, boundsToLeaflet, type FlyCommand } from '../components/map/GeoMap'
import MapScanner, { type MapScanStage } from '../components/map/MapScanner'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { useMapLayers } from '../hooks/useMapLayers'

const PRESETS = [
  { name: 'Vijayawada Benchmark', query: 'Vijayawada, Andhra Pradesh, India' },
  { name: 'Cologne / Rhine River', query: 'Cologne, Germany' },
  { name: 'Tokyo / Sumida River', query: 'Tokyo, Japan' },
  { name: 'London / Thames River', query: 'London, United Kingdom' },
  { name: 'New Orleans / Mississippi', query: 'New Orleans, Louisiana, USA' },
]

export default function RiskMap() {
  const location = useLocation()
  const locationState = location.state as { fromSearch?: boolean; targetArea?: StudyArea; timestamp?: number } | null

  // Map layers hook with target area awareness
  const { layers, error: layersError, refetch } = useMapLayers()
  const [riskMap, setRiskMap] = useState<RiskMapType | null>(null)
  const [riskLoading, setRiskLoading] = useState(false)

  // Explicit 5-stage loading state machine:
  // placeholder -> scanning -> area-found -> tiles-loading -> flying-to-area -> ready (or error)
  const [scanStage, setScanStage] = useState<MapScanStage>('idle')
  const [activeArea, setActiveArea] = useState<StudyArea | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [flyCommand, setFlyCommand] = useState<FlyCommand | null>(null)

  // In-page search bar state
  const [searchQuery, setSearchQuery] = useState('')
  const [suggestions, setSuggestions] = useState<LocationSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)

  // Sequence synchronization & cancellation tracking
  const sequenceIdRef = useRef(0)
  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([])
  const tilesReadyRef = useRef(false)

  const clearAllTimers = () => {
    timerRefs.current.forEach(clearTimeout)
    timerRefs.current = []
  }

  // Trigger camera flight to target bounds
  const triggerCameraFlight = useCallback((target: StudyArea, layersData?: any) => {
    const seqId = sequenceIdRef.current
    const targetBounds = boundsToLeaflet(
      target.bounding_box || layersData?.max_bounds || layersData?.boundary,
      target.center
    )
    const cmd: FlyCommand = {
      id: seqId,
      bounds: targetBounds,
      center: [target.center.lat, target.center.lon],
      duration: 1.1,
    }
    setFlyCommand(cmd)
    setScanStage('flying-to-area')
  }, [])

  // Orchestrate the multi-stage map loading sequence
  const executeMapSequence = useCallback((target: StudyArea) => {
    sequenceIdRef.current += 1
    const seqId = sequenceIdRef.current
    clearAllTimers()

    setActiveArea(target)
    setErrorMessage(null)
    setFlyCommand(null)
    tilesReadyRef.current = false

    // STAGE A: Placeholder (immediately renders container dimensions & GIS grid)
    setScanStage('placeholder')

    // Transition to STAGE B: Scanning after 350ms
    const t1 = setTimeout(async () => {
      if (sequenceIdRef.current !== seqId) return
      setScanStage('scanning')

      // Concurrently fetch layers for the chosen area while scanning animation runs
      const fetchPromise = refetch(target)
      // Enforce minimum scanning duration (1100ms) so the search trajectory is clearly perceived
      const minScanPromise = new Promise((resolve) => {
        const tScan = setTimeout(resolve, 1100)
        timerRefs.current.push(tScan as any)
      })

      try {
        const [layersData] = await Promise.all([fetchPromise, minScanPromise])
        if (sequenceIdRef.current !== seqId) return

        if (!layersData) {
          setScanStage('error')
          setErrorMessage('Could not load spatial boundary layers for this study area.')
          return
        }

        // STAGE C: Area Found (confirmation checkmark and coordinates lock-on)
        setScanStage('area-found')

        // Hold area-found confirmation for 800ms, then transition to STAGE D: Tiles Loading
        const t2 = setTimeout(() => {
          if (sequenceIdRef.current !== seqId) return
          setScanStage('tiles-loading')

          // If tiles are already ready from prior cache, transition immediately to camera flight
          if (tilesReadyRef.current) {
            const tQuick = setTimeout(() => {
              if (sequenceIdRef.current !== seqId) return
              triggerCameraFlight(target, layersData)
            }, 300)
            timerRefs.current.push(tQuick as any)
            return
          }

          // Otherwise wait for tile load, with a failsafe timer (1500ms)
          const tTilesSafety = setTimeout(() => {
            if (sequenceIdRef.current !== seqId) return
            triggerCameraFlight(target, layersData)
          }, 1500)
          timerRefs.current.push(tTilesSafety as any)
        }, 800)
        timerRefs.current.push(t2 as any)
      } catch (err: any) {
        if (sequenceIdRef.current !== seqId) return
        setScanStage('error')
        setErrorMessage(err?.message || 'Geocoding or boundary resolution failed.')
      }
    }, 350)
    timerRefs.current.push(t1 as any)
  }, [refetch, triggerCameraFlight])

  // TileLayer load event handler: mark tile readiness
  const handleTilesLoaded = useCallback(() => {
    tilesReadyRef.current = true
    if (scanStage === 'tiles-loading' && activeArea) {
      triggerCameraFlight(activeArea, layers)
    }
  }, [scanStage, activeArea, layers, triggerCameraFlight])

  // Camera flight completion callback from GeoMap
  const handleFlyComplete = useCallback((commandId: number) => {
    // Only accept completion for the currently active sequence
    if (commandId === sequenceIdRef.current && scanStage === 'flying-to-area') {
      setScanStage('ready')
    }
  }, [scanStage])

  // Detect arrival from search navigation or direct entry
  useEffect(() => {
    if (locationState?.fromSearch && locationState?.targetArea) {
      executeMapSequence(locationState.targetArea)
    } else {
      // First arrival without direct search: load active area context smoothly
      api.currentArea()
        .then((res) => {
          if (res.study_area) {
            setActiveArea(res.study_area)
            if (scanStage === 'idle') {
              setScanStage('ready')
            }
          }
        })
        .catch(() => {})
    }
  }, [locationState, executeMapSequence])

  // Clean up timers on unmount
  useEffect(() => {
    return () => clearAllTimers()
  }, [])

  // Load risk zones whenever active area or ready stage settles
  useEffect(() => {
    if (scanStage === 'ready') {
      setRiskLoading(true)
      api.riskZones()
        .then(setRiskMap)
        .catch(() => setRiskMap(null))
        .finally(() => setRiskLoading(false))
    }
  }, [scanStage])

  // In-page live search autocomplete
  useEffect(() => {
    if (!searchQuery || searchQuery.trim().length < 3) {
      setSuggestions([])
      return
    }

    const timer = setTimeout(async () => {
      setIsSearching(true)
      try {
        const res = await api.searchLocations(searchQuery.trim(), 4)
        setSuggestions(res.results || [])
      } catch {
        setSuggestions([])
      } finally {
        setIsSearching(false)
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [searchQuery])

  // Select area directly on Risk Map page
  const handleSelectQuery = async (queryText: string) => {
    setIsSearching(true)
    setSuggestions([])
    try {
      const res = await api.selectArea({ location_query: queryText, half_size_deg: 0.06 })
      if (res.status === 'OK' && res.study_area) {
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        setSearchQuery('')
        executeMapSequence(res.study_area)
      } else {
        setScanStage('error')
        setErrorMessage('Could not locate study area. Please try a different query.')
      }
    } catch (err: any) {
      setScanStage('error')
      setErrorMessage(err?.message || 'Failed to select study area.')
    } finally {
      setIsSearching(false)
    }
  }

  const handleSelectPreset = (presetQuery: string) => {
    handleSelectQuery(presetQuery)
  }

  const handleResetBenchmark = async () => {
    try {
      const res = await api.resetArea()
      if (res.status === 'OK' && res.study_area) {
        window.dispatchEvent(new CustomEvent('study-area-changed', { detail: res.study_area }))
        executeMapSequence(res.study_area)
      }
    } catch {}
  }

  const currentDisplayArea = activeArea || layers?.study_area
  const center: LatLngTuple = currentDisplayArea?.center
    ? [currentDisplayArea.center.lat, currentDisplayArea.center.lon]
    : [16.5061, 80.6050]

  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))

  return (
    <div className="flex flex-col gap-6 page-enter">
      {/* Module Header */}
      <div>
        <span className="eyebrow">Module 4 · Geospatial Risk Mapping</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Flood Risk Map</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          {currentDisplayArea?.scope_note ?? currentDisplayArea?.name ?? 'Vijayawada – Krishna River Corridor'}
        </p>
        <p className="text-ink-700 text-xs mt-2 max-w-2xl">
          Geometry mode: <span className="font-mono text-signal-teal">{layers?.geometry_mode || 'dynamic_grid'}</span> — river
          geometry loaded from spatial corridor dataset; risk zones use an adaptive grid spatial model.
        </p>
      </div>

      {/* In-Page Quick Location Search Bar & Presets */}
      <div className="panel p-4 bg-base-900/90 border border-base-700/80 rounded-lg shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-base-800">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-signal-teal status-glow" />
            <span className="font-mono text-xs uppercase tracking-wider text-ink-300 font-semibold">
              Search &amp; Calibrate Study Area
            </span>
          </div>
          <span className="font-mono text-[11px] text-ink-500">
            Current: <span className="text-signal-teal font-medium">{currentDisplayArea?.name || 'Vijayawada'}</span>
          </span>
        </div>

        {/* Search input with live autocomplete */}
        <div className="mt-3 relative">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Type city or river corridor (e.g., Tokyo, Cologne, London, New Orleans)..."
                disabled={scanStage === 'scanning' || scanStage === 'placeholder'}
                className="w-full bg-base-950 border border-base-600 rounded px-3 py-2 text-xs text-ink-100 placeholder-ink-600 focus:outline-none focus:border-signal-teal transition-colors"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && searchQuery.trim()) {
                    handleSelectQuery(searchQuery.trim())
                  }
                }}
              />
              {isSearching && (
                <div className="absolute right-3 top-2.5">
                  <span className="w-3.5 h-3.5 border-2 border-base-600 border-t-signal-teal rounded-full animate-spin inline-block" />
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => searchQuery.trim() && handleSelectQuery(searchQuery.trim())}
              disabled={!searchQuery.trim() || isSearching}
              className="bg-signal-teal text-base-950 font-medium px-4 py-2 rounded text-xs hover:bg-signal-teal/90 transition-colors shadow disabled:opacity-40"
            >
              Locate Area
            </button>
          </div>

          {/* Autocomplete suggestions dropdown */}
          {suggestions.length > 0 && (
            <div className="absolute z-40 left-0 right-0 mt-1 bg-base-950 border border-base-600 rounded shadow-2xl overflow-hidden divide-y divide-base-800">
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSelectQuery(s.display_name.split(',')[0])}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-base-800 transition-colors flex items-center justify-between"
                >
                  <span className="font-medium text-ink-100">
                    {s.city || s.display_name.split(',')[0]}
                  </span>
                  <span className="font-mono text-[10px] text-ink-500">
                    {s.latitude.toFixed(2)}°, {s.longitude.toFixed(2)}°
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Quick Presets row */}
        <div className="flex flex-wrap items-center gap-1.5 mt-3 pt-2">
          <span className="text-[10px] font-mono text-ink-500 uppercase mr-1">Presets:</span>
          {PRESETS.map((p) => (
            <button
              key={p.name}
              type="button"
              onClick={() => handleSelectPreset(p.query)}
              disabled={scanStage === 'scanning' || scanStage === 'placeholder'}
              className="px-2.5 py-1 rounded bg-base-950 border border-base-750 hover:border-signal-teal/50 hover:bg-base-800 text-[11px] text-ink-300 hover:text-signal-teal transition-all"
            >
              {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Main Map Viewport Container */}
      <div className="panel p-2 md:p-4 relative overflow-hidden" style={{ minHeight: '540px' }}>
        {/* Real Leaflet Map — Always rendered with stable container for smooth flying */}
        <GeoMap
          mapConfig={layers?.map_config}
          bounds={currentDisplayArea?.bounding_box || layers?.max_bounds}
          center={center}
          height="520px"
          onTilesLoaded={handleTilesLoaded}
          flyCommand={flyCommand}
          onFlyComplete={handleFlyComplete}
        >
          {layers && (
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name={layers.study_area?.river ? `${layers.study_area.river}` : 'River Centerline'} checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
            </LayersControl>
          )}
        </GeoMap>

        {/* Multi-stage Map Scanner & Transition Overlay */}
        <MapScanner
          stage={scanStage}
          locationName={currentDisplayArea?.name || 'Selected Study Area'}
          coordinates={currentDisplayArea?.center || null}
          boundsSummary={currentDisplayArea?.river ? `Corridor: ${currentDisplayArea.river}` : null}
          errorMessage={errorMessage || layersError}
          onRetry={() => currentDisplayArea && executeMapSequence(currentDisplayArea)}
          onResetBenchmark={handleResetBenchmark}
        />
      </div>

      {/* Risk Legend & Summary Info */}
      <RiskLegend riverName={currentDisplayArea?.river} />

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
