import { useEffect, useState, useRef, useCallback, useMemo, Fragment } from 'react'
import { useLocation } from 'react-router-dom'
import { Circle, CircleMarker, Popup } from 'react-leaflet'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError, getStoredStudyArea } from '../services/api'
import type {
  Candidate,
  OptimizationRunResponse,
  RiskMap as RiskMapType,
  QuantumOptimizationResponse,
  OptimizationComparisonResponse,
  StudyArea,
  RiskZone,
} from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import StatCard from '../components/StatCard'
import GeoMap, { LayersControl, LayersOverlay, boundsToLeaflet, type FlyCommand } from '../components/map/GeoMap'
import MapScanner, { type MapScanStage } from '../components/map/MapScanner'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer, RISK_COLORS } from '../components/map/baseLayers'
import RiskLegend from '../components/map/RiskLegend'
import {
  ConnectedSensorMapNodes,
  ConnectedMapCalloutOverlay,
  ConnectedSensorNodeBar,
  useCalculatedSensorIntelligence,
  type ActiveCalloutTarget,
} from '../components/map/ConnectedSensorIntelligence'
import SensorMapLegend from '../components/map/SensorMapLegend'
import { useMapLayers } from '../hooks/useMapLayers'

export default function SensorPlacement() {
  const location = useLocation()
  const locationState = location.state as {
    fromSearch?: boolean
    targetArea?: StudyArea
    timestamp?: number
    autoRun?: boolean
    numSensors?: number
    coverageRadius?: number
  } | null

  const { layers, loading: layersLoading, error: layersError, refetch } = useMapLayers()
  const [activeArea, setActiveArea] = useState<StudyArea | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMapType | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])

  // Optimization Parameters — use guided flow values if provided
  const [numSensors, setNumSensors] = useState(locationState?.numSensors ?? 8)
  const [radius, setRadius] = useState(locationState?.coverageRadius ?? 2.5)
  const [commRange, setCommRange] = useState(4.0)
  const [maxCommNodes, setMaxCommNodes] = useState(4)

  // Solver Results
  const [result, setResult] = useState<OptimizationRunResponse | null>(null)
  const [quantumResult, setQuantumResult] = useState<QuantumOptimizationResponse | null>(null)
  const [comparisonResult, setComparisonResult] = useState<OptimizationComparisonResponse | null>(null)
  const [activeSolverView, setActiveSolverView] = useState<'classical' | 'quantum'>('classical')

  // Execution States
  const [runningClassical, setRunningClassical] = useState(false)
  const [runningQuantum, setRunningQuantum] = useState(false)
  const [runningComparison, setRunningComparison] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Connected Callout & Selection State (Sensors, Candidates, Risk Zones)
  const [activeCallout, setActiveCallout] = useState<ActiveCalloutTarget | null>(null)
  const [hoveredSensorId, setHoveredSensorId] = useState<string | null>(null)
  const [selectedSensorId, setSelectedSensorId] = useState<string | null>(null)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Quantum QAOA Parameters
  const [qaoaDepth, setQaoaDepth] = useState(1)
  const [qaoaShots, setQaoaShots] = useState(1024)
  const [maxQuantumCandidates, setMaxQuantumCandidates] = useState(10)

  // Map Animation Sequence (MapScanner)
  const [scanStage, setScanStage] = useState<MapScanStage>('idle')
  const [flyCommand, setFlyCommand] = useState<FlyCommand | null>(null)
  const sequenceIdRef = useRef(0)
  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([])
  const autoRunTriggered = useRef(false)

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
    setError(null)
    setFlyCommand(null)

    // STAGE A: Placeholder
    setScanStage('placeholder')

    // STAGE B: Scanning
    const t1 = setTimeout(async () => {
      if (sequenceIdRef.current !== seqId) return
      setScanStage('scanning')

      const fetchPromise = refetch(target)
      const minScanPromise = new Promise((resolve) => {
        const tScan = setTimeout(resolve, 1100)
        timerRefs.current.push(tScan as any)
      })

      try {
        const [layersData] = await Promise.all([fetchPromise, minScanPromise])
        if (sequenceIdRef.current !== seqId) return

        if (!layersData) {
          setError('Could not load map layers for the chosen area.')
          setScanStage('error')
          return
        }

        // STAGE C: Area found
        setScanStage('area-found')

        const t3 = setTimeout(() => {
          if (sequenceIdRef.current !== seqId) return
          setScanStage('tiles-loading')

          const t4 = setTimeout(() => {
            if (sequenceIdRef.current !== seqId) return
            triggerCameraFlight(target, layersData)
          }, 350)
          timerRefs.current.push(t4)
        }, 600)
        timerRefs.current.push(t3)
      } catch (err: any) {
        if (sequenceIdRef.current !== seqId) return
        setError(err?.message || 'Error configuring study area layers.')
        setScanStage('error')
      }
    }, 350)
    timerRefs.current.push(t1)
  }, [refetch, triggerCameraFlight])

  // Auto-run classical placement (triggered by guided flow)
  const handleRunClassicalAuto = useCallback(async () => {
    setRunningClassical(true)
    setError(null)
    setScanStage('ready')
    const nSensors = locationState?.numSensors ?? numSensors
    const covRadius = locationState?.coverageRadius ?? radius
    try {
      const res = await api.runOptimization({
        num_sensors: nSensors,
        coverage_radius_km: covRadius,
        comm_range_km: commRange,
        max_comm_nodes: maxCommNodes,
      })
      setResult(res)
      setActiveSolverView('classical')
      const c = await api.candidates()
      setCandidates(c.candidates || [])

      // Strictly hover-only: no sensor explanation boxes visible on initial run or load
      setActiveCallout(null)
      setSelectedSensorId(null)
      setScanStage('ready')
    } catch (e: any) {
      setError(e instanceof ApiError ? e.message : 'Classical placement optimization failed.')
    } finally {
      setRunningClassical(false)
    }
  }, [locationState, numSensors, radius, commRange, maxCommNodes])

  // Handle camera flight completion — auto-run if guided flow
  const handleFlightComplete = useCallback(() => {
    setScanStage('ready')
    // Auto-run classical optimization if arriving from guided flow
    if (locationState?.autoRun && !autoRunTriggered.current) {
      autoRunTriggered.current = true
      setTimeout(() => {
        handleRunClassicalAuto()
      }, 350)
    }
  }, [locationState, handleRunClassicalAuto])

  // Initialize data and study area
  useEffect(() => {
    const target = locationState?.targetArea
    if (target) {
      setActiveArea(target)
      if (locationState?.fromSearch) {
        executeMapSequence(target)
      }
    } else {
      api.currentArea()
        .then((r) => {
          if (r.study_area) {
            setActiveArea(r.study_area)
            if (locationState?.fromSearch) {
              executeMapSequence(r.study_area)
            }
          }
        })
        .catch(() => {})
    }

    api.riskZones().then(setRiskMap).catch(() => setRiskMap(null))
    api.candidates().then((r) => setCandidates(r.candidates || [])).catch(() => setCandidates([]))

    // Fallback timer: if autoRun is active, trigger after 3.2s even if flight notification didn't fire
    let fallbackTimer: ReturnType<typeof setTimeout> | null = null
    if (locationState?.autoRun && !autoRunTriggered.current) {
      fallbackTimer = setTimeout(() => {
        if (!autoRunTriggered.current) {
          autoRunTriggered.current = true
          handleRunClassicalAuto()
        }
      }, 3200)
    }

    return () => {
      clearAllTimers()
      if (fallbackTimer) clearTimeout(fallbackTimer)
    }
  }, [locationState, executeMapSequence, handleRunClassicalAuto])

  // Run Classical Greedy Placement Optimization
  const handleRunClassical = async () => {
    setRunningClassical(true)
    setError(null)
    setScanStage('ready')
    try {
      const res = await api.runOptimization({
        num_sensors: numSensors,
        coverage_radius_km: radius,
        comm_range_km: commRange,
        max_comm_nodes: maxCommNodes,
      })
      setResult(res)
      setActiveSolverView('classical')
      const c = await api.candidates()
      setCandidates(c.candidates || [])

      // Strictly hover-only: no sensor explanation boxes visible on completion
      setActiveCallout(null)
      setSelectedSensorId(null)
      setScanStage('ready')
    } catch (e: any) {
      setError(e instanceof ApiError ? e.message : 'Classical placement optimization failed.')
    } finally {
      setRunningClassical(false)
    }
  }

  // Run QAOA Quantum Simulation
  const handleRunQuantum = async () => {
    setRunningQuantum(true)
    setError(null)
    setScanStage('ready')
    try {
      const qRes = await api.runQuantumOptimization({
        num_sensors: numSensors,
        coverage_radius_km: radius,
        p: qaoaDepth,
        shots: qaoaShots,
        max_candidates: maxQuantumCandidates,
      })
      setQuantumResult(qRes)
      setActiveSolverView('quantum')

      // Strictly hover-only: no sensor explanation boxes visible on completion
      setActiveCallout(null)
      setSelectedSensorId(null)
      setScanStage('ready')
    } catch (e: any) {
      setError(e instanceof ApiError ? e.message : 'Quantum QAOA statevector optimization failed.')
    } finally {
      setRunningQuantum(false)
    }
  }

  // Run Classical vs QAOA Comparison Benchmark
  const handleRunComparison = async () => {
    setRunningComparison(true)
    setError(null)
    try {
      const cmpRes = await api.compareOptimization({
        num_sensors: numSensors,
        coverage_radius_km: radius,
        p: qaoaDepth,
        shots: qaoaShots,
        max_candidates: maxQuantumCandidates,
      })
      setComparisonResult(cmpRes)
    } catch (e: any) {
      setError(e instanceof ApiError ? e.message : 'Solver comparison benchmark failed.')
    } finally {
      setRunningComparison(false)
    }
  }

  // Active solution sensors to render on map
  const activeSensors = (activeSolverView === 'quantum' && quantumResult)
    ? quantumResult.optimization.selected_sensors
    : (result?.optimization.selected_sensors ?? [])

  const disconnectedIds = useMemo(
    () => new Set(result?.connectivity?.disconnected_sensor_ids ?? []),
    [result]
  )

  // Grounded multi-criteria intelligence calculation for active sensors
  const calculatedIntelligence = useCalculatedSensorIntelligence({
    activeSensors,
    riskMap: riskMap || (layers?.zones ? ({ zones: layers.zones } as any) : null),
    studyArea: activeArea || layers?.study_area || null,
    numSensors,
    commRange,
    disconnectedIds,
    activeSolverView,
    qaoaDepth,
    qaoaShots,
  })

  // Timer helper for smooth, flicker-free mouse interaction
  const clearCloseTimer = useCallback(() => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
  }, [])

  // Sensor hover, leave, and click handlers (Strictly hover-only for placement callout boxes)
  const handleSensorHover = useCallback(
    (sensorId: string, lat: number, lon: number) => {
      clearCloseTimer()
      setHoveredSensorId(sensorId)
      setActiveCallout({
        type: 'sensor',
        id: sensorId,
        lat,
        lon,
        isPinned: false,
      })
    },
    [clearCloseTimer]
  )

  const handleSensorLeave = useCallback(() => {
    clearCloseTimer()
    closeTimerRef.current = setTimeout(() => {
      setHoveredSensorId(null)
      setActiveCallout((prev) => (prev?.type === 'sensor' ? null : prev))
    }, 280)
  }, [clearCloseTimer])

  const handleCenterNode = useCallback((lat: number, lon: number) => {
    if (!isFinite(lat) || !isFinite(lon)) return
    sequenceIdRef.current += 1
    const delta = 0.02
    setFlyCommand({
      id: sequenceIdRef.current,
      bounds: [
        [lat - delta, lon - delta],
        [lat + delta, lon + delta],
      ],
      center: [lat, lon],
      duration: 0.8,
    })
  }, [])

  const handleSensorClick = useCallback(
    (sensorId: string, lat: number, lon: number) => {
      clearCloseTimer()
      setSelectedSensorId(sensorId)
      handleCenterNode(lat, lon)
    },
    [clearCloseTimer, handleCenterNode]
  )

  // Candidate hover, leave, and click handlers
  const handleCandidateHover = useCallback(
    (candidate: Candidate, lat: number, lon: number) => {
      clearCloseTimer()
      setActiveCallout({
        type: 'candidate',
        id: candidate.candidate_id,
        lat,
        lon,
        data: candidate,
        isPinned: false,
      })
    },
    [clearCloseTimer]
  )

  const handleCandidateLeave = useCallback(() => {
    clearCloseTimer()
    closeTimerRef.current = setTimeout(() => {
      setActiveCallout((prev) => (prev?.type === 'candidate' ? null : prev))
    }, 280)
  }, [clearCloseTimer])

  const handleCandidateClick = useCallback(
    (candidate: Candidate, lat: number, lon: number) => {
      clearCloseTimer()
      handleCenterNode(lat, lon)
    },
    [clearCloseTimer, handleCenterNode]
  )

  // Risk zone hover and click handlers
  const handleZoneHover = useCallback(
    (zone: RiskZone | null, latLng?: LatLngTuple) => {
      if (!zone || !latLng) {
        clearCloseTimer()
        closeTimerRef.current = setTimeout(() => {
          setActiveCallout((prev) => (prev?.type === 'risk-zone' ? null : prev))
        }, 280)
        return
      }
      clearCloseTimer()
      setActiveCallout({
        type: 'risk-zone',
        id: zone.zone_id,
        lat: latLng[0],
        lon: latLng[1],
        data: zone,
        isPinned: false,
      })
    },
    [clearCloseTimer]
  )

  const handleZoneClick = useCallback(
    (zoneId: string) => {
      clearCloseTimer()
      const zone =
        layers?.zones?.find((z) => z.zone_id === zoneId) ||
        riskMap?.zones?.find((z) => z.zone_id === zoneId)
      if (zone?.bounds) {
        const cLat = (zone.bounds.min_lat + zone.bounds.max_lat) / 2
        const cLon = (zone.bounds.min_lon + zone.bounds.max_lon) / 2
        handleCenterNode(cLat, cLon)
      }
    },
    [clearCloseTimer, layers, riskMap, handleCenterNode]
  )

  // Callout Card anti-flicker enter & leave handlers
  const handleMouseEnterCard = useCallback(() => {
    clearCloseTimer()
  }, [clearCloseTimer])

  const handleMouseLeaveCard = useCallback(() => {
    clearCloseTimer()
    closeTimerRef.current = setTimeout(() => {
      setActiveCallout(null)
      setHoveredSensorId(null)
    }, 280)
  }, [clearCloseTimer])

  const handleDismissCallout = useCallback(() => {
    clearCloseTimer()
    setActiveCallout(null)
    setHoveredSensorId(null)
    setSelectedSensorId(null)
  }, [clearCloseTimer])

  const handleBarSelectSensor = useCallback(
    (sensorId: string, lat: number, lon: number) => {
      clearCloseTimer()
      setSelectedSensorId(sensorId)
      handleCenterNode(lat, lon)
    },
    [clearCloseTimer, handleCenterNode]
  )

  if (layersLoading && !layers) return <LoadingState label="Loading candidate geometry and river basin contours…" />
  if (layersError && !layers) return <ErrorState message={layersError ?? 'Map layers unavailable.'} />

  const currentCenter: LatLngTuple = layers?.study_area?.center
    ? [layers.study_area.center.lat, layers.study_area.center.lon]
    : [16.5062, 80.648]

  const effectiveZones = riskMap?.zones || layers?.zones || []
  const zoneRiskLookup = new Map(effectiveZones.map((z) => [z.zone_id, z]))
  const selectedIds = new Set(activeSensors.map((s) => s.candidate_id))
  const uncoveredZones = new Set(result?.optimization?.uncovered_priority_zone_ids ?? [])

  return (
    <div className="flex flex-col gap-8 page-enter">
      {/* Header & Area Breadcrumb */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-signal-teal mb-1">
          <span>SECTION 02</span>
          <span>/</span>
          <span>RESEARCH &amp; OPTIMIZATION</span>
        </div>
        <h1 className="font-display text-2xl sm:text-3xl text-ink-100 font-bold tracking-tight">
          Smart Sensor Placement
        </h1>
        <p className="text-ink-400 text-sm mt-1 max-w-3xl leading-relaxed">
          Comparing classical greedy heuristics against locally simulated Quantum Approximate Optimization Algorithm (QAOA)
          on Quadratic Unconstrained Binary Optimization (QUBO) formulations of flood-risk coverage.
        </p>

        {activeArea && (
          <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-900 border border-base-700 text-xs text-ink-300">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Study Area:</span>
            <strong className="text-ink-100 font-semibold">{activeArea.name}</strong>
            <span className="text-ink-500 font-mono">
              ({activeArea.center.lat.toFixed(4)}°N, {activeArea.center.lon.toFixed(4)}°E)
            </span>
          </div>
        )}
      </div>

      {/* Constraints & Optimizer Controls */}
      <div className="panel p-5 sm:p-6 border-base-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-base-700/60 pb-4">
          <div>
            <span className="eyebrow">Optimization Constraints</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">Sensor Budget &amp; Physical Parameters</h3>
          </div>

          {/* Map Overlay Toggle (Classical vs Quantum) */}
          {(result || quantumResult) && (
            <div className="flex items-center gap-2 bg-base-800 p-1 rounded-lg border border-base-700 text-xs">
              <span className="text-ink-400 px-2 font-mono text-[11px]">Map Display:</span>
              <button
                onClick={() => setActiveSolverView('classical')}
                disabled={!result}
                className={`min-h-[38px] px-3.5 py-1.5 rounded font-medium text-xs transition-colors ${
                  activeSolverView === 'classical'
                    ? 'bg-signal-teal text-base-950 font-bold shadow-sm'
                    : 'text-ink-300 hover:text-ink-100 disabled:opacity-40'
                }`}
              >
                Classical Greedy
              </button>
              <button
                onClick={() => setActiveSolverView('quantum')}
                disabled={!quantumResult}
                className={`min-h-[38px] px-3.5 py-1.5 rounded font-medium text-xs transition-colors ${
                  activeSolverView === 'quantum'
                    ? 'bg-signal-teal text-base-950 font-bold shadow-sm'
                    : 'text-ink-300 hover:text-ink-100 disabled:opacity-40'
                }`}
              >
                Quantum QAOA
              </button>
            </div>
          )}
        </div>

        {/* Inputs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-4">
          <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-base-950/40 border border-base-750/60">
            <label className="text-xs font-mono text-ink-300 font-medium flex items-center justify-between">
              <span>Sensor Budget (K):</span>
              <span className="text-signal-teal font-bold">{numSensors}</span>
            </label>
            <input
              type="range"
              min={1}
              max={24}
              value={numSensors}
              onChange={(e) => setNumSensors(Number(e.target.value))}
              className="accent-signal-teal cursor-pointer h-2 min-h-[36px]"
            />
            <span className="text-[10px] text-ink-500 font-mono">1 to 24 sensors</span>
          </div>

          <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-base-950/40 border border-base-750/60">
            <label className="text-xs font-mono text-ink-300 font-medium flex items-center justify-between">
              <span>Coverage Radius:</span>
              <span className="text-signal-teal font-bold">{radius} km</span>
            </label>
            <input
              type="range"
              min={0.5}
              max={8.0}
              step={0.1}
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="accent-signal-teal cursor-pointer h-2 min-h-[36px]"
            />
            <span className="text-[10px] text-ink-500 font-mono">Hydrological sensing horizon</span>
          </div>

          <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-base-950/40 border border-base-750/60">
            <label className="text-xs font-mono text-ink-300 font-medium flex items-center justify-between">
              <span>Comm Range:</span>
              <span className="text-signal-cyan font-bold">{commRange} km</span>
            </label>
            <input
              type="range"
              min={1.0}
              max={15.0}
              step={0.5}
              value={commRange}
              onChange={(e) => setCommRange(Number(e.target.value))}
              className="accent-signal-cyan cursor-pointer h-2 min-h-[36px]"
            />
            <span className="text-[10px] text-ink-500 font-mono">LoRa / mesh link limit</span>
          </div>

          <div className="flex flex-col gap-1.5 p-3 rounded-lg bg-base-950/40 border border-base-750/60">
            <label className="text-xs font-mono text-ink-300 font-medium flex items-center justify-between">
              <span>QAOA Depth:</span>
              <span className="text-purple-400 font-bold">p={qaoaDepth}</span>
            </label>
            <div className="flex gap-2 min-h-[36px] items-center">
              {[1, 2].map((pVal) => (
                <button
                  key={pVal}
                  onClick={() => setQaoaDepth(pVal)}
                  className={`flex-1 py-1.5 rounded text-xs font-mono border min-h-[36px] transition-colors ${
                    qaoaDepth === pVal
                      ? 'bg-purple-950/80 border-purple-500 text-purple-200 font-bold'
                      : 'border-base-700 bg-base-800 text-ink-400 hover:text-ink-200'
                  }`}
                >
                  p = {pVal}
                </button>
              ))}
            </div>
            <span className="text-[10px] text-ink-500 font-mono">Variational circuit depth</span>
          </div>
        </div>

        {/* Solver Execution Actions */}
        <div className="flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-2.5 sm:gap-3 mt-6 pt-4 border-t border-base-700/60">
          <button
            onClick={handleRunClassical}
            disabled={runningClassical || runningQuantum || runningComparison}
            className="w-full sm:w-auto min-h-[44px] bg-signal-teal text-base-950 font-bold px-4 py-2.5 rounded-lg hover:bg-signal-teal/90 disabled:opacity-40 transition-colors text-xs flex items-center justify-center gap-2 shrink-0"
          >
            {runningClassical ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-base-950 border-t-transparent rounded-full animate-spin" />
                <span>Running Classical Greedy…</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span>Run Classical Placement</span>
              </>
            )}
          </button>

          <button
            onClick={handleRunQuantum}
            disabled={runningClassical || runningQuantum || runningComparison}
            className="w-full sm:w-auto min-h-[44px] bg-purple-600/20 border border-purple-500/50 text-purple-200 font-bold px-4 py-2.5 rounded-lg hover:bg-purple-600/30 disabled:opacity-40 transition-colors text-xs flex items-center justify-center gap-2 shrink-0"
          >
            {runningQuantum ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-purple-300 border-t-transparent rounded-full animate-spin" />
                <span>Simulating QAOA Circuit…</span>
              </>
            ) : (
              <>
                <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                <span>Run QAOA Quantum Solver</span>
              </>
            )}
          </button>

          <button
            onClick={handleRunComparison}
            disabled={runningClassical || runningQuantum || runningComparison}
            className="w-full sm:w-auto min-h-[44px] border border-base-600 bg-base-800 text-ink-100 font-medium px-4 py-2.5 rounded-lg hover:bg-base-750 disabled:opacity-40 transition-colors text-xs flex items-center justify-center gap-2 shrink-0"
          >
            {runningComparison ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-ink-100 border-t-transparent rounded-full animate-spin" />
                <span>Evaluating Benchmark Comparison…</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4 text-signal-cyan" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <span>Compare Classical vs QAOA Benchmark</span>
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded bg-red-950/40 border border-red-500/50 text-red-200 text-xs">
            {error}
          </div>
        )}
      </div>

      {/* Metrics Row (When result exists) */}
      {(result || quantumResult) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatCard
            label="Sensors Placed"
            value={activeSensors.length}
            sublabel={`Budget: ${numSensors} allowed`}
            accent="teal"
          />
          <StatCard
            label="Coverage Ratio"
            value={
              activeSolverView === 'quantum' && quantumResult
                ? (quantumResult.optimization?.coverage_percentage ?? 0)
                : (result?.optimization?.coverage_percentage ?? 0)
            }
            unit="%"
            accent="teal"
          />
          <StatCard
            label="Critical Risk Coverage"
            value={
              activeSolverView === 'quantum' && quantumResult
                ? (quantumResult.optimization?.critical_zone_coverage_percentage ?? 0)
                : (result?.optimization?.critical_zone_coverage_percentage ?? 0)
            }
            unit="%"
            accent="critical"
          />
          <StatCard
            label="Solver Mode"
            value={activeSolverView === 'quantum' ? 'QAOA (Sim)' : 'Classical Greedy'}
            sublabel={
              activeSolverView === 'quantum'
                ? `Depth p=${qaoaDepth}, ${qaoaShots} shots`
                : 'Polynomial-time (1-1/e) approx'
            }
            accent={activeSolverView === 'quantum' ? 'moderate' : 'low'}
          />
        </div>
      )}

      {/* Unified Geospatial Solution & Connected Sensor Intelligence */}
      <div className="panel p-4 sm:p-6 flex flex-col gap-4 border-base-700 bg-base-900/90 shadow-xl">
        {/* Section Header */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 pb-3 border-b border-base-750">
          <div>
            <div className="flex items-center gap-2">
              <span className="eyebrow">Geospatial Intelligence Engine</span>
              {activeSensors.length > 0 && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono bg-signal-teal/15 text-signal-teal border border-signal-teal/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-signal-teal animate-pulse" />
                  <span>{activeSensors.length} Nodes Placed</span>
                </span>
              )}
            </div>
            <h3 className="font-display text-lg text-ink-100 font-semibold mt-0.5">
              Sensor Footprints &amp; Multi-Criteria Telemetry
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              {activeArea?.name || layers?.study_area?.name || 'Active Study Area'} &bull; River:{' '}
              <span className="text-signal-teal font-medium">{layers?.study_area?.river || activeArea?.river || 'Main River'}</span> &bull; Budget:{' '}
              <span className="font-mono text-ink-200">K={numSensors}</span> &bull; Radius:{' '}
              <span className="font-mono text-ink-200">{radius} km</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-ink-300">
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-base-950/70 border border-base-750">
              <span className="w-2.5 h-2.5 rounded-full bg-signal-teal border border-base-950" />
              <span>Optimized Node</span>
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-base-950/70 border border-base-750">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400 border border-base-950" />
              <span>Selected Node</span>
            </span>
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-base-950/70 border border-base-750">
              <span className="w-2.5 h-2.5 rounded-full border border-signal-teal/60 bg-signal-teal/20" />
              <span>Coverage ({radius}km)</span>
            </span>
          </div>
        </div>

        {/* Sensor Node Bar: Quick 1-click center and hover preview */}
        {activeSensors.length > 0 ? (
          <ConnectedSensorNodeBar
            activeSensors={activeSensors}
            selectedSensorId={selectedSensorId}
            hoveredSensorId={hoveredSensorId}
            disconnectedIds={disconnectedIds}
            onSelectSensor={handleBarSelectSensor}
            onHoverSensor={handleSensorHover}
            onLeaveSensor={handleSensorLeave}
          />
        ) : (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-3.5 py-2.5 rounded-lg bg-base-950/70 border border-base-750 text-xs text-ink-300">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-signal-teal/60" />
              <span>No sensors placed yet. Run classical or quantum optimization to deploy sensors along the river corridor.</span>
            </div>
            <button
              type="button"
              onClick={handleRunClassical}
              disabled={runningClassical || runningQuantum || runningComparison}
              className="bg-signal-teal text-base-950 font-semibold px-3 py-1 rounded text-xs hover:bg-signal-teal/90 transition-colors shadow shrink-0"
            >
              Run Placement Now
            </button>
          </div>
        )}

        {/* Full-Width Map Canvas with Connected Intelligence Floating Callouts */}
        <div className="relative rounded-xl overflow-hidden border border-base-700 bg-base-950 shadow-inner h-[380px] sm:h-[480px] lg:h-[640px] xl:h-[700px] w-full">
          {/* MapScanner Animation Overlay */}
          <MapScanner
            stage={scanStage}
            locationName={activeArea?.name || 'Active Study Area'}
            coordinates={activeArea?.center}
            onReady={() => setScanStage('ready')}
          />

          {layers && (
            <GeoMap
              mapConfig={layers.map_config}
              bounds={layers.max_bounds}
              center={currentCenter}
              height="100%"
              flyCommand={flyCommand}
              onFlyComplete={handleFlightComplete}
            >
              <LayersControl position="topright">
                <LayersOverlay name="Study Area Boundary" checked>
                  <StudyAreaBoundaryLayer boundary={layers.boundary} />
                </LayersOverlay>

                <LayersOverlay name={layers.study_area?.river || 'Waterway Centerline'} checked>
                  <RiverLayer river={layers.river} />
                </LayersOverlay>

                <LayersOverlay name="Flood Risk Zones" checked>
                  <RiskZoneLayer
                    zones={layers.zones}
                    riskLookup={zoneRiskLookup}
                    onZoneClick={handleZoneClick}
                    onZoneHover={handleZoneHover}
                  />
                </LayersOverlay>

                <LayersOverlay name="Candidate Locations" checked>
                  <>
                    {candidates
                      .filter((c) => !selectedIds.has(c.candidate_id))
                      .map((c) => {
                        const cLat = Number(c.lat ?? (c as any).latitude)
                        const cLon = Number(c.lon ?? (c as any).longitude)
                        if (!isFinite(cLat) || !isFinite(cLon)) return null

                        const isCallout =
                          activeCallout?.type === 'candidate' && activeCallout?.id === c.candidate_id

                        return (
                          <CircleMarker
                            key={c.candidate_id}
                            center={[cLat, cLon]}
                            radius={isCallout ? 6 : 4}
                            pathOptions={{
                              color: isCallout ? '#38bdf8' : '#0ea5e9',
                              fillColor: isCallout ? '#38bdf8' : '#0ea5e9',
                              fillOpacity: isCallout ? 0.9 : 0.5,
                              weight: isCallout ? 2 : 1,
                            }}
                            eventHandlers={{
                              mouseover: () => handleCandidateHover(c, cLat, cLon),
                              mouseout: () => handleCandidateLeave(),
                              click: () => handleCandidateClick(c, cLat, cLon),
                            }}
                          />
                        )
                      })}
                  </>
                </LayersOverlay>
              </LayersControl>

              {/* Connected Intelligence Map Nodes: Glowing Numbered Nodes & Translucent Coverage Footprints */}
              <ConnectedSensorMapNodes
                activeSensors={activeSensors}
                selectedSensorId={selectedSensorId}
                hoveredSensorId={hoveredSensorId}
                radius={radius}
                disconnectedIds={disconnectedIds}
                onHoverSensor={handleSensorHover}
                onLeaveSensor={handleSensorLeave}
                onClickSensor={handleSensorClick}
              />

              {/* Dynamic SVG Curved Connector Line & Floating Dark Glass Callout Card */}
              <ConnectedMapCalloutOverlay
                activeCallout={activeCallout}
                onDismiss={handleDismissCallout}
                calculatedIntelligence={calculatedIntelligence}
                activeSensors={activeSensors}
                disconnectedIds={disconnectedIds}
                candidates={candidates}
                riskMap={riskMap || (layers?.zones ? ({ zones: layers.zones } as any) : null)}
                studyArea={activeArea || layers?.study_area || null}
                numSensors={numSensors}
                radius={radius}
                commRange={commRange}
                activeSolverView={activeSolverView}
                onMouseEnterCard={handleMouseEnterCard}
                onMouseLeaveCard={handleMouseLeaveCard}
              />

              {/* Compact Map Symbology & Flood Risk Legend (Collapsible, Bottom-Left) */}
              <SensorMapLegend
                riverName={layers.study_area?.river || activeArea?.river}
                coverageRadiusKm={radius}
                numSensorsPlaced={activeSensors.length}
                candidatesCount={candidates.length}
                uncoveredCount={uncoveredZones.size}
              />
            </GeoMap>
          )}
        </div>
      </div>

      {/* Side-by-Side Comparison Matrix (Classical vs QAOA) */}
      {comparisonResult && (
        <div className="panel p-6 border-signal-teal/40 bg-base-900/90">
          <div className="flex items-center justify-between border-b border-base-700/60 pb-3">
            <div>
              <span className="eyebrow">Direct Benchmark</span>
              <h3 className="font-display text-xl text-ink-100 font-semibold">
                Classical Greedy vs QAOA Quantum Simulation
              </h3>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-ink-300 border border-base-700">
              Evaluated on {comparisonResult.problem_size.num_candidates} Candidate Nodes
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
            {/* Classical Card */}
            <div className="p-4 rounded-lg bg-base-850 border border-base-700/80 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <h4 className="font-display font-semibold text-ink-100 text-base">Classical Greedy Heuristic</h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-base-750 text-ink-300">
                    Polynomial Baseline
                  </span>
                </div>
                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Sensors Selected:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.classical_result.num_sensors_selected}
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Weighted Risk Coverage:</span>
                    <strong className="text-signal-teal font-mono">
                      {comparisonResult.classical_result.weighted_coverage.toFixed(2)}
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Total Coverage %:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.classical_result.coverage_percentage.toFixed(1)}%
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Critical Zone Coverage %:</span>
                    <strong className="text-risk-critical font-mono">
                      {comparisonResult.classical_result.critical_zone_coverage_pct.toFixed(1)}%
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Runtime:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.classical_result.execution_time_ms.toFixed(1)} ms
                    </strong>
                  </div>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-base-750 text-[11px] text-ink-400">
                Selected Nodes: <code className="text-ink-200">{comparisonResult.classical_result.selected_sensor_ids.join(', ')}</code>
              </div>
            </div>

            {/* Quantum Card */}
            <div className="p-4 rounded-lg bg-base-850 border border-purple-500/40 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <h4 className="font-display font-semibold text-purple-200 text-base">QAOA Quantum Solver</h4>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950/80 text-purple-300 border border-purple-500/30">
                    Statevector p={comparisonResult.quantum_result.qaoa_depth_p}
                  </span>
                </div>
                <div className="mt-4 space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Sensors Selected:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.quantum_result.num_sensors_selected}
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Weighted Risk Coverage:</span>
                    <strong className="text-purple-300 font-mono">
                      {comparisonResult.quantum_result.weighted_coverage.toFixed(2)}
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Total Coverage %:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.quantum_result.coverage_percentage.toFixed(1)}%
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Critical Zone Coverage %:</span>
                    <strong className="text-risk-critical font-mono">
                      {comparisonResult.quantum_result.critical_zone_coverage_pct.toFixed(1)}%
                    </strong>
                  </div>
                  <div className="flex justify-between py-1 border-b border-base-750">
                    <span className="text-ink-400">Circuit Simulation Time:</span>
                    <strong className="text-ink-100 font-mono">
                      {comparisonResult.quantum_result.execution_time_ms.toFixed(1)} ms
                    </strong>
                  </div>
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-base-750 text-[11px] text-ink-400">
                Solution Feasibility: <strong className="text-emerald-400">{comparisonResult.quantum_result.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}</strong> · QUBO Energy: <code className="text-purple-300">{comparisonResult.quantum_result.qubo_energy?.toFixed(3)}</code>
              </div>
            </div>
          </div>

          {/* Ground truth note if available */}
          {comparisonResult.exhaustive_ground_truth && (
            <div className="mt-4 p-3 rounded bg-base-950 border border-base-800 text-xs text-ink-400 flex items-center justify-between">
              <span>Exhaustive Ground Truth Optimum (Exact Combinatorial Search):</span>
              <strong className="text-signal-teal font-mono">
                {comparisonResult.exhaustive_ground_truth.optimal_weighted_coverage.toFixed(2)} ({comparisonResult.exhaustive_ground_truth.optimal_coverage_percentage.toFixed(1)}%)
              </strong>
            </div>
          )}
        </div>
      )}

      {/* Placement Formulation & Mathematical Rigor */}
      <div className="panel p-6 border-base-700">
        <span className="eyebrow">Mathematical Formulation</span>
        <h3 className="font-display text-lg text-ink-100 font-semibold mt-1">
          QUBO Mapping for Quantum Approximate Optimization
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4 text-xs text-ink-300 leading-relaxed">
          <div className="space-y-3">
            <h4 className="font-semibold text-ink-100">1. Problem Definition</h4>
            <p>
              Given a candidate set of sensor locations <code className="text-signal-teal">C</code> and a collection of flood risk zones <code className="text-signal-teal">Z</code> with risk weights <code className="text-signal-teal">w_j</code>, we seek a subset of size <code className="text-signal-teal">K</code> that maximizes total covered risk weight.
            </p>
            <div className="p-3 rounded bg-base-900 border border-base-750 font-mono text-[11px] text-ink-200">
              max ∑ (w_j · y_j) subject to ∑ x_i ≤ K, y_j ≤ ∑ a_ij x_i
            </div>
          </div>

          <div className="space-y-3">
            <h4 className="font-semibold text-ink-100">2. Ising / QUBO Hamiltonian</h4>
            <p>
              The constrained maximization is converted into quadratic minimization via quadratic penalty formulation:
            </p>
            <div className="p-3 rounded bg-base-900 border border-base-750 font-mono text-[11px] text-ink-200">
              {'H(x) = - ∑ c_i x_i + λ_penalty · (∑ x_i - K)² + ∑_{overlap} γ_ij x_i x_j'}
            </div>
            <p className="text-[11px] text-ink-500">
              Where λ_penalty enforces the sensor budget constraint and γ_ij penalizes sensor coverage overlaps.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
