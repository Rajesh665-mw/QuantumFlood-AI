import { useEffect, useState, Fragment } from 'react'
import { Circle, CircleMarker, Popup } from 'react-leaflet'
import type { LatLngTuple } from 'leaflet'
import { api, ApiError } from '../services/api'
import type {
  Candidate,
  OptimizationRunResponse,
  RiskMap as RiskMapType,
  QuantumOptimizationResponse,
  OptimizationComparisonResponse,
} from '../types'
import { LoadingState, ErrorState, EmptyState } from '../components/LoadingState'
import StatCard from '../components/StatCard'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer, RISK_COLORS } from '../components/map/baseLayers'
import RiskLegend from '../components/map/RiskLegend'
import { useMapLayers } from '../hooks/useMapLayers'

export default function SensorOptimisation() {
  const { layers, loading, error: layersError } = useMapLayers()
  const [riskMap, setRiskMap] = useState<RiskMapType | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [numSensors, setNumSensors] = useState(8)
  const [radius, setRadius] = useState(2.5)
  const [commRange, setCommRange] = useState(4.0)
  const [maxCommNodes, setMaxCommNodes] = useState(4)
  const [result, setResult] = useState<OptimizationRunResponse | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Quantum QAOA and Comparison State
  const [quantumResult, setQuantumResult] = useState<QuantumOptimizationResponse | null>(null)
  const [comparisonResult, setComparisonResult] = useState<OptimizationComparisonResponse | null>(null)
  const [qaoaDepth, setQaoaDepth] = useState(1)
  const [qaoaShots, setQaoaShots] = useState(1024)
  const [maxQuantumCandidates, setMaxQuantumCandidates] = useState(10)
  const [quantumRunning, setQuantumRunning] = useState(false)
  const [quantumError, setQuantumError] = useState<string | null>(null)
  const [activeSolverView, setActiveSolverView] = useState<'classical' | 'quantum'>('classical')

  useEffect(() => {
    api.riskZones().then(setRiskMap).catch(() => setRiskMap(null))
    api.candidates().then((r) => setCandidates(r.candidates)).catch(() => setCandidates([]))
  }, [])

  const runOptimization = async () => {
    setRunning(true)
    setError(null)
    try {
      const res = await api.runOptimization({
        num_sensors: numSensors, coverage_radius_km: radius, comm_range_km: commRange, max_comm_nodes: maxCommNodes,
      })
      setResult(res)
      const c = await api.candidates()
      setCandidates(c.candidates)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Optimisation failed. Generate a risk map first (Flood Forecasting page).')
    } finally {
      setRunning(false)
    }
  }

  const runQuantum = async () => {
    setQuantumRunning(true)
    setQuantumError(null)
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
    } catch (e) {
      setQuantumError(e instanceof ApiError ? e.message : 'Quantum QAOA optimisation failed.')
    } finally {
      setQuantumRunning(false)
    }
  }

  const runComparison = async () => {
    setQuantumRunning(true)
    setQuantumError(null)
    try {
      const cmpRes = await api.compareOptimization({
        num_sensors: numSensors,
        coverage_radius_km: radius,
        p: qaoaDepth,
        shots: qaoaShots,
        max_candidates: maxQuantumCandidates,
      })
      setComparisonResult(cmpRes)
    } catch (e) {
      setQuantumError(e instanceof ApiError ? e.message : 'Solver comparison failed.')
    } finally {
      setQuantumRunning(false)
    }
  }

  if (loading) return <LoadingState label="Loading candidate geometry…" />
  if (layersError || !layers) return <ErrorState message={layersError ?? 'Map layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  
  // Dynamic active sensors depending on whether classical or quantum solution is selected for map
  const activeSensors = (activeSolverView === 'quantum' && quantumResult)
    ? quantumResult.optimization.selected_sensors
    : (result?.optimization.selected_sensors ?? [])
  const selectedIds = new Set(activeSensors.map((s) => s.candidate_id))
  const disconnectedIds = new Set(result?.connectivity.disconnected_sensor_ids ?? [])
  const uncoveredZones = new Set(result?.optimization.uncovered_priority_zone_ids ?? [])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="eyebrow">Module 6 · Sensor Placement Optimisation</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">Sensor Placement & Quantum QAOA</h1>
        <p className="text-ink-500 text-sm mt-2 max-w-2xl">
          Weighted maximum-coverage problem, solvable via classical greedy approximation or
          experimental Quantum Approximate Optimization Algorithm (QAOA). Optimizes coverage of
          flood-risk-weighted zones under an exact sensor budget K.
        </p>
      </div>

      {!riskMap && (
        <div className="panel p-4 text-sm text-ink-300 border-signal-tealDim/40">
          No risk map available yet. Visit <a href="/forecasting" className="text-signal-teal underline">Flood Forecasting</a> and run a forecast + risk generation first — optimisation needs zone risk scores to weight coverage.
        </div>
      )}

      {/* Classical Optimization Controls */}
      <div className="panel p-5">
        <div className="flex items-center justify-between">
          <span className="data-label">Optimisation Constraints</span>
          {quantumResult && result && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-ink-500">Map Overlay:</span>
              <button
                onClick={() => setActiveSolverView('classical')}
                className={`px-2.5 py-1 rounded font-mono text-[11px] transition-colors ${
                  activeSolverView === 'classical'
                    ? 'bg-signal-teal text-base-950 font-semibold'
                    : 'bg-base-700 text-ink-300 hover:text-ink-100'
                }`}
              >
                Classical
              </button>
              <button
                onClick={() => setActiveSolverView('quantum')}
                className={`px-2.5 py-1 rounded font-mono text-[11px] transition-colors ${
                  activeSolverView === 'quantum'
                    ? 'bg-signal-teal text-base-950 font-semibold'
                    : 'bg-base-700 text-ink-300 hover:text-ink-100'
                }`}
              >
                Quantum QAOA
              </button>
            </div>
          )}
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-3">
          <Control label="Number of sensors" value={numSensors} min={1} max={30} onChange={setNumSensors} />
          <Control label="Coverage radius (km)" value={radius} min={0.5} max={10} step={0.1} onChange={setRadius} />
          <Control label="Comm range (km)" value={commRange} min={0.5} max={15} step={0.1} onChange={setCommRange} />
          <Control label="Max comm nodes" value={maxCommNodes} min={1} max={20} onChange={setMaxCommNodes} />
        </div>
        <div className="flex flex-wrap gap-3 mt-5">
          <button
            onClick={runOptimization}
            disabled={running || !riskMap}
            className="bg-signal-teal text-base-950 font-medium px-5 py-2.5 rounded hover:bg-signal-teal/90 disabled:opacity-40 transition-colors"
          >
            {running ? 'Running classical solver…' : 'Run Classical Optimisation'}
          </button>
          <button
            onClick={runComparison}
            disabled={quantumRunning || !riskMap}
            className="border border-signal-teal/50 text-signal-teal font-medium px-5 py-2.5 rounded hover:bg-signal-teal/10 disabled:opacity-40 transition-colors"
          >
            {quantumRunning ? 'Executing quantum comparison…' : 'Compare Classical vs Quantum (QAOA)'}
          </button>
        </div>
        {error && riskMap && <p className="text-risk-critical text-sm mt-3">{error}</p>}
      </div>

      {/* Classical Stats */}
      {result && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Sensors Selected" value={result.optimization.num_sensors_selected} sublabel={`of ${result.optimization.num_sensors_requested} requested`} />
          <StatCard label="Total Coverage" value={result.optimization.coverage_percentage} unit="%" accent="teal" />
          <StatCard label="Critical Coverage" value={result.optimization.critical_zone_coverage_percentage} unit="%" accent="critical" />
          <StatCard
            label="Comm Nodes Used"
            value={`${result.connectivity.comm_nodes_used}/${result.connectivity.max_comm_nodes}`}
            sublabel={result.connectivity.budget_exhausted ? 'Budget exhausted' : 'Within budget'}
            accent={result.connectivity.budget_exhausted ? 'moderate' : 'low'}
          />
        </div>
      )}

      {/* Map */}
      <div className="panel p-2 md:p-4">
        <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
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
            <LayersOverlay name="Candidate Locations" checked={!result && !quantumResult}>
              <>
                {candidates.filter((c) => !selectedIds.has(c.candidate_id)).map((c) => (
                  <CircleMarker
                    key={c.candidate_id}
                    center={[c.lat, c.lon]}
                    radius={4}
                    pathOptions={{ color: '#5A6779', fillColor: '#5A6779', fillOpacity: 0.6, weight: 1 }}
                  >
                    <Popup>
                      <div className="font-mono text-xs leading-relaxed">
                        <div className="font-semibold">{c.candidate_id}</div>
                        <div>Zone: {c.zone_id}</div>
                        <div>Method: {c.placement_method === 'PULLED_TOWARD_RIVER_GEOMETRY' ? 'Pulled toward river' : 'Zone centroid'}</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </>
            </LayersOverlay>
            <LayersOverlay name="Selected Sensors + Coverage" checked>
              <>
                {activeSensors.map((s) => (
                  <Fragment key={s.candidate_id}>
                    <Circle center={[s.lat, s.lon]} radius={radius * 1000} pathOptions={{ color: '#2DD4BF', weight: 1, fillOpacity: 0.05 }} />
                    <CircleMarker
                      center={[s.lat, s.lon]}
                      radius={6}
                      pathOptions={{
                        color: disconnectedIds.has(s.candidate_id) ? '#D2504A' : '#2DD4BF',
                        fillColor: disconnectedIds.has(s.candidate_id) ? '#D2504A' : '#2DD4BF',
                        fillOpacity: 1,
                        weight: 2,
                      }}
                    >
                      <Popup>
                        <div className="font-mono text-xs leading-relaxed">
                          <div className="font-semibold">{s.candidate_id} ({activeSolverView === 'quantum' ? 'Quantum QAOA' : 'Classical Sensor'})</div>
                          <div>Zone: {s.zone_id}</div>
                          <div>Coverage radius: {radius} km</div>
                          <div>Zones covered: {s.covered_zone_ids.length}</div>
                          <div>Status: {disconnectedIds.has(s.candidate_id) ? 'DISCONNECTED' : 'Connected'}</div>
                        </div>
                      </Popup>
                    </CircleMarker>
                  </Fragment>
                ))}
              </>
            </LayersOverlay>
            <LayersOverlay name="Communication Nodes" checked>
              <>
                {(result?.connectivity.comm_nodes ?? []).map((n) => (
                  <CircleMarker key={n.comm_node_id} center={[n.lat, n.lon]} radius={10} pathOptions={{ color: '#C99A3B', fillOpacity: 0, weight: 2 }}>
                    <Popup>
                      <div className="font-mono text-xs leading-relaxed">
                        <div className="font-semibold">{n.comm_node_id}</div>
                        <div>Connected sensors: {n.connects_sensor_ids.length}</div>
                        <div>Comm range: {commRange} km</div>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </>
            </LayersOverlay>
          </LayersControl>
        </GeoMap>
      </div>

      <RiskLegend riverName={layers.study_area.river} />

      <div className="panel p-4 flex flex-wrap items-center gap-4 text-xs text-ink-500">
        <LegendDot color="#5A6779" label="Unselected candidate" />
        <LegendDot color="#2DD4BF" label={`Selected sensor (${activeSolverView === 'quantum' ? 'Quantum' : 'Classical'})`} />
        <LegendDot color="#D2504A" label="Selected sensor (disconnected)" />
        <LegendDot color="#C99A3B" label="Communication node" outline />
      </div>

      {/* ========================================================================= */}
      {/* QUANTUM QAOA & COMPARISON SECTION                                          */}
      {/* ========================================================================= */}
      <div className="panel p-5 border-l-4 border-l-signal-teal bg-base-900/90">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-base-700 pb-4">
          <div>
            <span className="eyebrow text-signal-teal">Quantum Layer · Variational Approximation</span>
            <h2 className="font-display text-lg text-ink-100 font-semibold mt-0.5">
              Quantum Approximate Optimization Algorithm (QAOA)
            </h2>
            <p className="text-ink-400 text-xs mt-1 max-w-2xl leading-relaxed">
              Maps the Sensor Placement QUBO onto an Ising Cost Hamiltonian and optimizes parameterized
              alternating unitaries U(H_C, &gamma;) and U(H_M, &beta;) using local statevector simulation.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={runQuantum}
              disabled={quantumRunning || !riskMap}
              className="bg-signal-teal text-base-950 font-medium px-4 py-2 rounded text-xs hover:bg-signal-teal/90 disabled:opacity-40 transition-colors"
            >
              {quantumRunning ? 'Simulating QAOA…' : 'Run Quantum QAOA'}
            </button>
            <button
              onClick={runComparison}
              disabled={quantumRunning || !riskMap}
              className="border border-base-500 text-ink-200 font-medium px-4 py-2 rounded text-xs hover:bg-base-800 disabled:opacity-40 transition-colors"
            >
              Compare All Solvers
            </button>
          </div>
        </div>

        {/* QAOA Parameters */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-1">
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-ink-500">QAOA Depth (p)</span>
            <select
              value={qaoaDepth}
              onChange={(e) => setQaoaDepth(Number(e.target.value))}
              className="bg-base-800 border border-base-600 rounded px-2.5 py-1.5 text-xs text-ink-100 font-mono"
            >
              <option value={1}>p = 1 (Fast)</option>
              <option value={2}>p = 2 (Higher Fidelity)</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-ink-500">Measurement Shots</span>
            <select
              value={qaoaShots}
              onChange={(e) => setQaoaShots(Number(e.target.value))}
              className="bg-base-800 border border-base-600 rounded px-2.5 py-1.5 text-xs text-ink-100 font-mono"
            >
              <option value={512}>512 shots</option>
              <option value={1024}>1024 shots</option>
              <option value={2048}>2048 shots</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="text-ink-500">Quantum Candidate Pool</span>
            <select
              value={maxQuantumCandidates}
              onChange={(e) => setMaxQuantumCandidates(Number(e.target.value))}
              className="bg-base-800 border border-base-600 rounded px-2.5 py-1.5 text-xs text-ink-100 font-mono"
            >
              <option value={8}>8 candidates (2^8 = 256 states)</option>
              <option value={10}>10 candidates (2^10 = 1024 states)</option>
              <option value={12}>12 candidates (2^12 = 4096 states)</option>
            </select>
          </label>
          <div className="flex flex-col justify-end text-xs">
            <span className="text-ink-500">Simulator Engine</span>
            <span className="font-mono text-signal-teal mt-1">Pure NumPy Statevector</span>
          </div>
        </div>

        {quantumError && <p className="text-risk-critical text-xs mt-3">{quantumError}</p>}

        {/* Standalone Quantum QAOA Results Card */}
        {quantumResult && !comparisonResult && (
          <div className="mt-5 panel p-4 border-signal-teal/40 bg-base-800/80">
            <div className="flex items-center justify-between text-xs text-signal-teal font-mono">
              <span className="font-semibold">QUANTUM QAOA OPTIMISATION RESULT</span>
              <span className="px-2 py-0.5 rounded text-[10px] bg-signal-teal/10 border border-signal-teal/30">
                {quantumResult.quantum_metrics.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
              <div>
                <span className="text-xs text-ink-500">Weighted Risk</span>
                <p className="text-lg font-display font-semibold text-signal-teal">{quantumResult.optimization.weighted_coverage}</p>
              </div>
              <div>
                <span className="text-xs text-ink-500">Coverage</span>
                <p className="text-lg font-display font-semibold text-ink-100">{quantumResult.optimization.coverage_percentage}%</p>
              </div>
              <div>
                <span className="text-xs text-ink-500">Sensors Selected</span>
                <p className="text-lg font-display font-semibold text-ink-100">{quantumResult.optimization.num_sensors_selected}</p>
              </div>
              <div>
                <span className="text-xs text-ink-500">Simulator Time</span>
                <p className="text-lg font-display font-semibold text-ink-100">{quantumResult.quantum_metrics.execution_time_ms} ms</p>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-base-700/60 flex flex-wrap gap-4 text-xs font-mono text-ink-400">
              <span>Qubits: <span className="text-ink-200">{quantumResult.quantum_metrics.qubits_used}</span></span>
              <span>QAOA Depth p: <span className="text-ink-200">{quantumResult.quantum_metrics.qaoa_depth_p}</span></span>
              <span>Shots: <span className="text-ink-200">{quantumResult.quantum_metrics.shots}</span></span>
              <span>Optimal Energy: <span className="text-ink-200">{quantumResult.quantum_metrics.optimal_energy.toFixed(3)}</span></span>
              <span>Sample Probability: <span className="text-ink-200">{(quantumResult.quantum_metrics.sample_probability * 100).toFixed(2)}%</span></span>
              <span>Selected Sensors: <span className="text-ink-200">{quantumResult.optimization.selected_sensors.map(s => s.candidate_id).join(', ')}</span></span>
            </div>
          </div>
        )}

        {/* Comparison Results Card */}
        {comparisonResult && (
          <div className="mt-5 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Classical Box */}
              <div className="panel p-4 border-base-600/80 bg-base-800/80">
                <div className="flex items-center justify-between text-xs text-ink-400 font-mono">
                  <span>CLASSICAL GREEDY</span>
                  <span>(1 &minus; 1/e)</span>
                </div>
                <div className="mt-2 text-xl font-display font-semibold text-ink-100">
                  {comparisonResult.classical_result.weighted_coverage}
                  <span className="text-xs font-mono text-ink-500 ml-1.5">weighted risk</span>
                </div>
                <div className="mt-2 space-y-1 text-xs text-ink-400 font-mono">
                  <div>Coverage: <span className="text-ink-100 font-semibold">{comparisonResult.classical_result.coverage_percentage}%</span></div>
                  <div>Coverage / Sensor: <span className="text-ink-100 font-semibold">{comparisonResult.classical_result.coverage_per_sensor ?? (comparisonResult.classical_result.weighted_coverage / Math.max(1, comparisonResult.classical_result.num_sensors_selected)).toFixed(2)}</span></div>
                  <div>Sensors: <span className="text-ink-100">{comparisonResult.classical_result.selected_sensor_ids.join(', ')}</span></div>
                  <div>Runtime: <span className="text-ink-100">{comparisonResult.classical_result.execution_time_ms} ms</span></div>
                </div>
              </div>

              {/* Quantum QAOA Box */}
              <div className="panel p-4 border-signal-teal/40 bg-base-800/80 relative overflow-hidden">
                <div className="flex items-center justify-between text-xs text-signal-teal font-mono">
                  <span>QUANTUM QAOA</span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-signal-teal/10 border border-signal-teal/30">
                    {comparisonResult.quantum_result.is_feasible ? 'FEASIBLE' : 'INFEASIBLE'}
                  </span>
                </div>
                <div className="mt-2 text-xl font-display font-semibold text-signal-teal">
                  {comparisonResult.quantum_result.weighted_coverage}
                  <span className="text-xs font-mono text-ink-500 ml-1.5">weighted risk</span>
                </div>
                <div className="mt-2 space-y-1 text-xs text-ink-400 font-mono">
                  <div>Coverage: <span className="text-ink-100 font-semibold">{comparisonResult.quantum_result.coverage_percentage}%</span></div>
                  <div>Coverage / Sensor: <span className="text-ink-100 font-semibold">{comparisonResult.quantum_result.coverage_per_sensor ?? (comparisonResult.quantum_result.weighted_coverage / Math.max(1, comparisonResult.quantum_result.num_sensors_selected)).toFixed(2)}</span></div>
                  <div>Sensors: <span className="text-ink-100">{comparisonResult.quantum_result.selected_sensor_ids.join(', ')}</span></div>
                  <div>Runtime: <span className="text-ink-100">{comparisonResult.quantum_result.execution_time_ms} ms</span> (p={comparisonResult.quantum_result.qaoa_depth_p})</div>
                  <div>Sample Prob: <span className="text-ink-100">{(comparisonResult.quantum_result.solution_probability * 100).toFixed(2)}%</span></div>
                </div>
              </div>

              {/* Exhaustive Ground Truth Box */}
              <div className="panel p-4 border-base-600/80 bg-base-800/80">
                <div className="flex items-center justify-between text-xs text-ink-400 font-mono">
                  <span>EXHAUSTIVE OPTIMUM</span>
                  <span>Combinatorial</span>
                </div>
                {comparisonResult.exhaustive_ground_truth ? (
                  <>
                    <div className="mt-2 text-xl font-display font-semibold text-ink-100">
                      {comparisonResult.exhaustive_ground_truth.optimal_weighted_coverage}
                      <span className="text-xs font-mono text-ink-500 ml-1.5">max possible</span>
                    </div>
                    <div className="mt-2 space-y-1 text-xs text-ink-400 font-mono">
                      <div>Coverage: <span className="text-ink-100 font-semibold">{comparisonResult.exhaustive_ground_truth.optimal_coverage_percentage}%</span></div>
                      <div>Combinations: <span className="text-ink-100">{comparisonResult.exhaustive_ground_truth.total_subsets_evaluated} evaluated</span></div>
                      <div>Optimum Match: <span className={comparisonResult.comparison_metrics.quantum_matched_global_optimum ? 'text-signal-teal font-semibold' : 'text-ink-300'}>
                        {comparisonResult.comparison_metrics.quantum_matched_global_optimum ? 'YES (100% Global Optimum)' : `${(comparisonResult.comparison_metrics.quantum_approximation_ratio! * 100).toFixed(1)}%`}
                      </span></div>
                    </div>
                  </>
                ) : (
                  <div className="mt-4 text-xs text-ink-500 font-mono leading-relaxed">
                    Search space exceeded real-time interactive limit (N &gt; 12).
                  </div>
                )}
              </div>
            </div>

            {/* Communication Node Telemetry Comparison (Stage 2) */}
            {comparisonResult.communication_nodes_analysis && (
              <div className="panel p-4 bg-base-900/90 border-base-700/80 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs uppercase tracking-wider text-ink-300 font-semibold flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-signal-blue" />
                    Communication Node & Network Connectivity (Stage 2 Telemetry)
                  </span>
                  <span className="text-[11px] font-mono text-ink-400">
                    Range: {comparisonResult.communication_nodes_analysis.comm_range_km.toFixed(1)} km | Max Nodes Budget: {comparisonResult.communication_nodes_analysis.max_comm_nodes_budget}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
                  <div className="p-3 rounded bg-base-800/80 border border-base-700/60 space-y-1.5">
                    <div className="text-ink-400 font-semibold flex justify-between">
                      <span>CLASSICAL TOPOLOGY</span>
                      <span className="text-signal-teal">{comparisonResult.communication_nodes_analysis.classical.connectivity_percentage}% Connected</span>
                    </div>
                    <div className="text-ink-300">Sensors: <span className="text-ink-100">{comparisonResult.communication_nodes_analysis.classical.sensor_nodes_count}</span> | Relays Used: <span className="text-ink-100">{comparisonResult.communication_nodes_analysis.classical.comm_nodes_used} / {comparisonResult.communication_nodes_analysis.classical.max_comm_nodes_allowed}</span></div>
                    <div className="text-ink-300">Disconnected Sensors: <span className={comparisonResult.communication_nodes_analysis.classical.disconnected_nodes_count > 0 ? 'text-risk-high' : 'text-signal-teal'}>{comparisonResult.communication_nodes_analysis.classical.disconnected_nodes_count}</span></div>
                  </div>
                  <div className="p-3 rounded bg-base-800/80 border border-base-700/60 space-y-1.5">
                    <div className="text-ink-400 font-semibold flex justify-between">
                      <span>QUANTUM TOPOLOGY</span>
                      <span className="text-signal-teal">{comparisonResult.communication_nodes_analysis.quantum.connectivity_percentage}% Connected</span>
                    </div>
                    <div className="text-ink-300">Sensors: <span className="text-ink-100">{comparisonResult.communication_nodes_analysis.quantum.sensor_nodes_count}</span> | Relays Used: <span className="text-ink-100">{comparisonResult.communication_nodes_analysis.quantum.comm_nodes_used} / {comparisonResult.communication_nodes_analysis.quantum.max_comm_nodes_allowed}</span></div>
                    <div className="text-ink-300">Disconnected Sensors: <span className={comparisonResult.communication_nodes_analysis.quantum.disconnected_nodes_count > 0 ? 'text-risk-high' : 'text-signal-teal'}>{comparisonResult.communication_nodes_analysis.quantum.disconnected_nodes_count}</span></div>
                  </div>
                </div>
              </div>
            )}

            {/* Minimal Nodes & Maximal Coverage Analysis (Target A Pareto Frontier) */}
            {comparisonResult.minimal_nodes_analysis && (
              <div className="panel p-4 bg-base-900/90 border-base-700/80 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-signal-teal" />
                    <span className="font-mono text-xs uppercase tracking-wider text-ink-300 font-semibold">
                      UC-067 Target A: Maximal Coverage with Minimal Nodes
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs font-mono">
                    <span className="px-2 py-0.5 rounded bg-signal-teal/15 text-signal-teal border border-signal-teal/40 font-semibold">
                      Recommended Minimal Sensors (k*): {comparisonResult.minimal_nodes_analysis.recommended_min_sensors}
                    </span>
                    <span className="text-ink-400">
                      Max Coverage: {comparisonResult.minimal_nodes_analysis.max_coverage_percentage}% ({comparisonResult.minimal_nodes_analysis.max_achievable_coverage} risk)
                    </span>
                  </div>
                </div>

                <p className="text-xs text-ink-300 font-body leading-relaxed">
                  {comparisonResult.minimal_nodes_analysis.efficiency_analysis}
                </p>

                {/* Pareto Frontier Table */}
                <div className="overflow-x-auto mt-2">
                  <table className="w-full text-left text-xs font-mono border-collapse">
                    <thead>
                      <tr className="border-b border-base-700 text-ink-400 bg-base-800/40">
                        <th className="p-2">Nodes (k)</th>
                        <th className="p-2">Weighted Coverage</th>
                        <th className="p-2">Coverage %</th>
                        <th className="p-2">Marginal Gain</th>
                        <th className="p-2">Coverage / Node</th>
                        <th className="p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-base-800">
                      {comparisonResult.minimal_nodes_analysis.pareto_frontier.map((row) => (
                        <tr
                          key={row.sensors_k}
                          className={row.is_minimal_optimum ? 'bg-signal-teal/10 font-semibold text-signal-teal' : 'text-ink-300 hover:bg-base-800/50'}
                        >
                          <td className="p-2">{row.sensors_k}</td>
                          <td className="p-2">{row.max_coverage.toFixed(1)}</td>
                          <td className="p-2">{row.coverage_percentage.toFixed(1)}%</td>
                          <td className="p-2">+{row.marginal_gain.toFixed(1)}</td>
                          <td className="p-2">{row.coverage_per_sensor.toFixed(2)}</td>
                          <td className="p-2">
                            {row.is_minimal_optimum ? (
                              <span className="px-1.5 py-0.5 rounded text-[10px] bg-signal-teal/20 border border-signal-teal/50 text-signal-teal uppercase">
                                Minimal Optimum (k*)
                              </span>
                            ) : (
                              <span className="text-ink-500 text-[10px]">
                                {row.marginal_gain > 0 ? 'Expanding' : 'Saturated'}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Academic Assessment Callout */}
            <div className="panel p-4 bg-base-950/70 border-base-700/80 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-signal-teal" />
                <span className="font-mono text-xs uppercase tracking-wider text-ink-300 font-semibold">
                  Algorithmic Assessment
                </span>
              </div>
              <p className="text-sm text-ink-200 leading-relaxed font-body">
                {comparisonResult.academic_assessment}
              </p>
              <div className="text-[11px] text-ink-500 border-t border-base-800 pt-2 flex flex-wrap justify-between items-center">
                <span>Academic Verification Note: Zero unproven quantum advantage is claimed. Classical greedy remains the production baseline.</span>
                <span className="font-mono text-signal-teal">Jaccard Sensor Similarity: {(comparisonResult.comparison_metrics.jaccard_similarity * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {result && result.optimization.uncovered_priority_zone_ids.length > 0 && (
        <div className="panel p-5 border-risk-high/30">
          <span className="data-label">Uncovered Priority Zones</span>
          <div className="flex flex-wrap gap-2 mt-3">
            {result.optimization.uncovered_priority_zone_ids.map((zid) => {
              const z = zoneRiskLookup.get(zid)
              return (
                <span
                  key={zid}
                  className={`font-mono text-xs px-2 py-1 rounded border ${
                    z?.risk_level === 'CRITICAL' ? 'text-risk-critical border-risk-critical/40 bg-risk-criticalBg' : 'text-ink-300 bg-base-700 border-base-600'
                  }`}
                >
                  {zid} {z && `(${z.risk_level})`}
                </span>
              )
            })}
          </div>
        </div>
      )}

      {result && result.connectivity.budget_exhausted && (
        <div className="panel p-5 border-risk-moderate/30">
          <span className="data-label text-risk-moderate">Communication Node Budget Exhausted</span>
          <p className="text-ink-300 text-sm mt-2">
            {result.connectivity.comm_nodes_used} of {result.connectivity.max_comm_nodes} communication nodes
            were used, but {result.connectivity.disconnected_sensor_ids.length} sensor(s) remain outside range.
            Increase the comm-node budget or comm range, or accept the current disconnected sensors as a
            known operational gap.
          </p>
        </div>
      )}

      {!result && riskMap && (
        <EmptyState title="No optimisation run yet" description="Configure constraints above and click 'Run Classical Optimisation' or 'Compare Classical vs Quantum' to solve the sensor placement problem." />
      )}
    </div>
  )
}

function Control({
  label, value, min, max, step = 1, onChange,
}: { label: string; value: number; min: number; max: number; step?: number; onChange: (v: number) => void }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-xs text-ink-500 flex justify-between">
        <span>{label}</span>
        <span className="font-mono text-signal-teal">{value}</span>
      </span>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="accent-signal-teal"
      />
    </label>
  )
}

function LegendDot({ color, label, outline = false }: { color: string; label: string; outline?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="w-3 h-3 rounded-full inline-block"
        style={outline ? { border: `2px solid ${color}` } : { backgroundColor: color }}
      />
      <span>{label}</span>
    </div>
  )
}
