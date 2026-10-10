import { useEffect, useState } from 'react'
import type { LatLngTuple } from 'leaflet'
import { api } from '../services/api'
import type { ResourceAllocationResponse, RiskMap } from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import GeoMap, { LayersControl, LayersOverlay } from '../components/map/GeoMap'
import { StudyAreaBoundaryLayer, RiverLayer, RiskZoneLayer } from '../components/map/baseLayers'
import { ResourceAllocationLayer } from '../components/map/GeoMapLayerExtensions'
import { useMapLayers } from '../hooks/useMapLayers'

export default function ResourceAllocation() {
  const { layers, loading: mapLoading, error: mapError } = useMapLayers()
  const [data, setData] = useState<ResourceAllocationResponse | null>(null)
  const [riskMap, setRiskMap] = useState<RiskMap | null>(null)
  const [loading, setLoading] = useState(true)
  const [allocating, setAllocating] = useState(false)

  // Configurable resource quantities
  const [rescueTeams, setRescueTeams] = useState(5)
  const [medicalTeams, setMedicalTeams] = useState(3)
  const [reliefUnits, setReliefUnits] = useState(4)
  const [vehicles, setVehicles] = useState(4)
  const [minRisk, setMinRisk] = useState('MODERATE')

  useEffect(() => {
    Promise.all([
      api.latestAllocations().catch(() => null),
      api.riskZones().catch(() => null),
    ])
      .then(([alloc, rm]) => {
        if (alloc) setData(alloc)
        if (rm) setRiskMap(rm)
      })
      .finally(() => setLoading(false))
  }, [])

  const handleAllocate = async () => {
    setAllocating(true)
    try {
      const res = await api.allocateResources({
        rescue_teams: rescueTeams,
        medical_teams: medicalTeams,
        relief_units: reliefUnits,
        emergency_vehicles: vehicles,
        min_risk_level: minRisk,
      })
      setData(res)
    } catch (err) {
      console.error('Failed to allocate resources:', err)
    } finally {
      setAllocating(false)
    }
  }

  if (mapLoading || loading) return <LoadingState label="Loading emergency resource allocation…" />
  if (mapError || !layers) return <ErrorState message={mapError ?? 'Geospatial layers unavailable.'} />

  const center: LatLngTuple = [layers.study_area.center.lat, layers.study_area.center.lon]
  const zoneRiskLookup = new Map((riskMap?.zones ?? []).map((z) => [z.zone_id, z]))
  const summary = data?.summary
  const allocations = data?.allocations ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <span className="eyebrow">Module 5 · Tactical Logistics &amp; Relief Planning</span>
        <h1 className="font-display text-2xl text-ink-100 mt-1">
          Emergency Resource Allocation
        </h1>
        <p className="text-ink-500 text-sm mt-2 max-w-3xl">
          Constrained optimization distributing user-specified emergency units (rescue squads, medical teams,
          relief depots, and amphibious/emergency vehicles) across high-risk zones based on vulnerability priority.
        </p>
      </div>

      {/* Honesty Banner */}
      <div className="panel p-4 bg-base-900/80 border-signal-teal/30 flex items-start gap-3">
        <span className="w-2 h-2 rounded-full bg-signal-teal mt-1.5 shrink-0" />
        <div className="text-xs text-ink-300 leading-relaxed">
          <strong className="text-signal-teal">Simulation Integrity Notice:</strong> Resource availability
          quantities are user-configured simulation parameters, not claims of actual government stockpile levels.
          The algorithm guarantees deterministic mathematical distribution across vulnerable zones respecting
          budget caps and operational capacity limits.
        </div>
      </div>

      {/* Control Grid + Map */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="panel p-5 space-y-4">
          <h2 className="font-display font-semibold text-sm text-ink-100 border-b border-base-600/60 pb-3">
            Available Resource Budgets
          </h2>

          <div className="space-y-3 font-mono text-xs">
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-ink-300">Rescue Teams</span>
                <span className="text-signal-teal font-bold">{rescueTeams} squads</span>
              </div>
              <input
                type="range"
                min="0"
                max="15"
                value={rescueTeams}
                onChange={(e) => setRescueTeams(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-ink-300">Medical Teams</span>
                <span className="text-signal-teal font-bold">{medicalTeams} units</span>
              </div>
              <input
                type="range"
                min="0"
                max="10"
                value={medicalTeams}
                onChange={(e) => setMedicalTeams(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-ink-300">Relief Units</span>
                <span className="text-signal-teal font-bold">{reliefUnits} depots</span>
              </div>
              <input
                type="range"
                min="0"
                max="15"
                value={reliefUnits}
                onChange={(e) => setReliefUnits(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div>
              <div className="flex justify-between mb-1">
                <span className="text-ink-300">Emergency Vehicles</span>
                <span className="text-signal-teal font-bold">{vehicles} vehicles</span>
              </div>
              <input
                type="range"
                min="0"
                max="15"
                value={vehicles}
                onChange={(e) => setVehicles(parseInt(e.target.value))}
                className="w-full accent-signal-teal cursor-pointer"
              />
            </div>

            <div className="pt-2 border-t border-base-600/60">
              <label className="data-label block mb-1">Eligibility Threshold</label>
              <select
                value={minRisk}
                onChange={(e) => setMinRisk(e.target.value)}
                className="w-full bg-base-900 border border-base-600 text-ink-100 text-xs rounded p-2 focus:border-signal-teal outline-none"
              >
                <option value="HIGH">HIGH &amp; CRITICAL Zones Only</option>
                <option value="MODERATE">MODERATE, HIGH &amp; CRITICAL Zones</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleAllocate}
            disabled={allocating}
            className="w-full mt-3 py-2.5 px-4 rounded bg-signal-teal text-base-950 font-display font-semibold text-xs tracking-wide uppercase hover:bg-signal-tealDim transition-colors shadow-sm disabled:opacity-50"
          >
            {allocating ? 'Optimising Allocations…' : 'Allocate Resources'}
          </button>
        </div>

        {/* Map */}
        <div className="lg:col-span-3 panel p-2 md:p-3 relative">
          <GeoMap mapConfig={layers.map_config} bounds={layers.max_bounds} center={center} height="520px">
            <LayersControl position="topright">
              <LayersOverlay name="Study Area Boundary" checked>
                <StudyAreaBoundaryLayer boundary={layers.boundary} />
              </LayersOverlay>
              <LayersOverlay name={layers.study_area?.river ? `${layers.study_area.river}` : 'River Centerline'} checked>
                <RiverLayer river={layers.river} />
              </LayersOverlay>
              <LayersOverlay name="Modelled Flood Risk Zones" checked>
                <RiskZoneLayer zones={layers.zones} riskLookup={zoneRiskLookup} />
              </LayersOverlay>
              <LayersOverlay name="Resource Allocation Badges" checked>
                <ResourceAllocationLayer allocations={allocations} />
              </LayersOverlay>
            </LayersControl>
          </GeoMap>
        </div>
      </div>

      {/* Allocation Summary Cards */}
      {summary && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="panel p-4 border-l-2 border-purple-400">
              <span className="data-label block">Serviced Zones</span>
              <span className="font-mono text-2xl font-bold text-ink-100 mt-1 block">
                {summary.zones_serviced_count} / {summary.eligible_zones_count}
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                Eligible zones receiving assistance
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-emerald-400">
              <span className="data-label block">Rescue Teams Deployed</span>
              <span className="font-mono text-2xl font-bold text-emerald-400 mt-1 block">
                {summary.allocated_quantities.rescue_teams}
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                {summary.unallocated_quantities.rescue_teams} in reserve
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-blue-400">
              <span className="data-label block">Medical Teams Deployed</span>
              <span className="font-mono text-2xl font-bold text-blue-400 mt-1 block">
                {summary.allocated_quantities.medical_teams}
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                {summary.unallocated_quantities.medical_teams} in reserve
              </span>
            </div>

            <div className="panel p-4 border-l-2 border-amber-400">
              <span className="data-label block">Vehicles &amp; Relief Units</span>
              <span className="font-mono text-2xl font-bold text-amber-400 mt-1 block">
                {summary.allocated_quantities.emergency_vehicles + summary.allocated_quantities.relief_units}
              </span>
              <span className="text-[11px] font-mono text-ink-500">
                Logistics &amp; transport deployed
              </span>
            </div>
          </div>

          {/* Allocation Table */}
          <div className="panel p-5 space-y-3">
            <h3 className="font-display font-semibold text-sm text-ink-100">
              Zone Priority Allocation Breakdown
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="text-ink-500 border-b border-base-600 text-left">
                    <th className="py-2.5 px-3">Zone ID</th>
                    <th className="py-2.5 px-3">Risk Level</th>
                    <th className="py-2.5 px-3">Priority Score</th>
                    <th className="py-2.5 px-3">River Standoff</th>
                    <th className="py-2.5 px-3">Allocated Units</th>
                    <th className="py-2.5 px-3">Allocation Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-base-700/50 text-ink-200">
                  {allocations.map((alloc) => (
                    <tr key={alloc.zone_id} className="hover:bg-base-700/30">
                      <td className="py-2.5 px-3 font-semibold text-ink-100">{alloc.zone_id}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`font-semibold ${
                            alloc.risk_level === 'CRITICAL'
                              ? 'text-red-400'
                              : alloc.risk_level === 'HIGH'
                              ? 'text-amber-400'
                              : 'text-yellow-400'
                          }`}
                        >
                          {alloc.risk_level}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-signal-teal font-bold">{alloc.priority_score}</td>
                      <td className="py-2.5 px-3">{alloc.distance_to_river_km} km</td>
                      <td className="py-2.5 px-3 font-medium text-ink-100">
                        {Object.entries(alloc.allocated_resources)
                          .filter(([_, count]) => count > 0)
                          .map(([res, count]) => `${count} ${res.replace(/_teams|_units/g, '')}`)
                          .join(', ')}
                      </td>
                      <td className="py-2.5 px-3 text-ink-300 max-w-md">{alloc.explanation}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Quantum-Readiness Formulation Box */}
          <div className="panel p-5 bg-base-900/60 border-base-700 space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between border-b border-base-700 pb-2">
              <span className="eyebrow">Mathematical Formulation · Quantum-Readiness</span>
              <span className="text-signal-teal text-[10px]">INTEGER KNAPSACK / QUBO</span>
            </div>
            <div className="text-ink-300 space-y-1 mt-2">
              <div><strong>Objective:</strong> {data?.mathematical_formulation?.objective}</div>
              <div><strong>Decision Variables:</strong> {data?.mathematical_formulation?.decision_variables}</div>
              <div>
                <strong>Constraints:</strong>
                <ul className="list-disc pl-4 space-y-0.5 text-ink-400 mt-1">
                  {data?.mathematical_formulation?.constraints.map((c, idx) => (
                    <li key={idx}>{c}</li>
                  ))}
                </ul>
              </div>
              <div className="pt-2 text-signal-teal text-[11px]">
                {data?.mathematical_formulation?.quantum_readiness}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
