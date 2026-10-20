import { useEffect, useState } from 'react'
import { api, ApiError } from '../services/api'
import type {
  ShelterRequest,
  InventoryItem,
  DemandSummaryResponse,
  AuditLogEntry,
  ResourceAllocationResponse,
  StudyArea,
  QuantumResourceAllocationResponse,
} from '../types'
import { LoadingState, ErrorState } from '../components/LoadingState'
import StatCard from '../components/StatCard'

const URGENCY_BADGES: Record<string, string> = {
  LOW: 'text-emerald-400 bg-emerald-950/60 border-emerald-500/30',
  MODERATE: 'text-sky-400 bg-sky-950/60 border-sky-500/30',
  HIGH: 'text-amber-400 bg-amber-950/60 border-amber-500/30',
  CRITICAL: 'text-red-400 bg-red-950/60 border-red-500/30 animate-pulse',
}

const STATUS_BADGES: Record<string, string> = {
  PENDING: 'text-amber-400 bg-amber-950/40 border-amber-500/30',
  PARTIALLY_ALLOCATED: 'text-sky-400 bg-sky-950/40 border-sky-500/30',
  ALLOCATED: 'text-purple-400 bg-purple-950/40 border-purple-500/30',
  PARTIALLY_FULFILLED: 'text-teal-400 bg-teal-950/40 border-teal-500/30',
  FULFILLED: 'text-emerald-400 bg-emerald-950/40 border-emerald-500/30',
}

export default function ResourcePlanning() {
  const [studyArea, setStudyArea] = useState<StudyArea | null>(null)
  const [requests, setRequests] = useState<ShelterRequest[]>([])
  const [inventory, setInventory] = useState<InventoryItem[]>([])
  const [demandSummary, setDemandSummary] = useState<DemandSummaryResponse | null>(null)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [fieldAlloc, setFieldAlloc] = useState<ResourceAllocationResponse | null>(null)

  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  // Interactive inline allocation state
  const [activeAllocReq, setActiveAllocReq] = useState<ShelterRequest | null>(null)
  const [customAllocQty, setCustomAllocQty] = useState<number>(0)
  const [activeFulfillReq, setActiveFulfillReq] = useState<ShelterRequest | null>(null)
  const [customFulfillQty, setCustomFulfillQty] = useState<number>(0)

  // Tactical Knapsack settings
  const [tacticalRescueTeams, setTacticalRescueTeams] = useState(8)
  const [tacticalMedicalUnits, setTacticalMedicalUnits] = useState(6)
  const [tacticalReliefSupplies, setTacticalReliefSupplies] = useState(15)
  const [tacticalVehicles, setTacticalVehicles] = useState(5)
  const [tacticalLoading, setTacticalLoading] = useState(false)

  // Hybrid Quantum Resource Knapsack Allocation State (Milestone 4)
  const [quantumAllocResult, setQuantumAllocResult] = useState<QuantumResourceAllocationResponse | null>(null)
  const [quantumResourceTarget, setQuantumResourceTarget] = useState('Clean Drinking Water (L)')
  const [quantumAllocLoading, setQuantumAllocLoading] = useState(false)
  const [quantumApplyLoading, setQuantumApplyLoading] = useState(false)
  const [quantumAllocError, setQuantumAllocError] = useState<string | null>(null)

  const handleRunQuantumAlloc = async () => {
    setQuantumAllocLoading(true)
    setQuantumAllocError(null)
    try {
      const res = await api.optimizeResourceKnapsack({
        resource_type: quantumResourceTarget,
      })
      setQuantumAllocResult(res)
    } catch (err: any) {
      setQuantumAllocError(err?.message || 'Failed to execute quantum knapsack optimization.')
    } finally {
      setQuantumAllocLoading(false)
    }
  }

  const handleApplyQuantumAlloc = async () => {
    if (!quantumAllocResult) return
    setQuantumApplyLoading(true)
    try {
      const payload = {
        allocations: quantumAllocResult.allocations.map((a) => ({
          request_id: a.request_id,
          allocated_quantity: a.allocated_quantity,
        })),
      }
      await api.applyQuantumResourceAllocation(payload)
      await loadData()
      setActionMessage({
        text: `Successfully applied ${quantumAllocResult.allocations.length} quantum-recommended allocations to ledger.`,
        type: 'success',
      })
    } catch (err: any) {
      setActionMessage({
        text: err?.message || 'Failed to apply allocations.',
        type: 'error',
      })
    } finally {
      setQuantumApplyLoading(false)
    }
  }

  const loadData = async () => {
    try {
      const [areaRes, reqs, inv, demand, logs, field] = await Promise.all([
        api.currentArea().catch(() => null),
        api.listShelterRequests().catch(() => ({ requests: [] })),
        api.getInventory().catch(() => ({ inventory: [] })),
        api.getDemandSummary().catch(() => null),
        api.getAuditLog().catch(() => ({ audit_trail: [] })),
        api.latestAllocations().catch(() => null),
      ])

      if (areaRes?.study_area) setStudyArea(areaRes.study_area)
      setRequests(reqs.requests || [])
      setInventory(inv.inventory || [])
      setDemandSummary(demand)
      setAuditLog(logs.audit_trail || [])
      setFieldAlloc(field)
    } catch (err: any) {
      console.error('Error loading resource planning data:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Helper to find inventory item for a request
  const getInventoryForItem = (resourceType: string): InventoryItem | undefined => {
    return inventory.find((inv) =>
      resourceType.toLowerCase().includes(inv.category.toLowerCase()) ||
      resourceType.toLowerCase().includes(inv.item.toLowerCase())
    )
  }

  // Handle Inventory Allocation to a Shelter Request
  const handleAllocate = async (req: ShelterRequest, quantity?: number) => {
    setActionLoading(true)
    setActionMessage(null)
    const toAllocate = quantity !== undefined && quantity > 0 ? quantity : (customAllocQty > 0 ? customAllocQty : req.requested_quantity)

    const invItem = getInventoryForItem(req.resource_type)
    if (invItem && toAllocate > invItem.available) {
      setActionMessage({
        text: `Cannot allocate ${toAllocate} units: only ${invItem.available} units available in stock.`,
        type: 'error',
      })
      setActionLoading(false)
      return
    }

    try {
      const res = await api.allocateShelterRequest({
        request_id: req.id,
        allocated_quantity: toAllocate,
      })
      setActionMessage({
        text: `Allocated ${toAllocate} units to ${req.shelter_name}. Request status: ${res.request.status}`,
        type: 'success',
      })
      setActiveAllocReq(null)
      loadData()
    } catch (err: any) {
      setActionMessage({
        text: err?.message || 'Allocation failed. Ensure requested amount does not exceed available warehouse stock.',
        type: 'error',
      })
    } finally {
      setActionLoading(false)
    }
  }

  // Handle Delivery Fulfillment
  const handleFulfill = async (req: ShelterRequest, quantity?: number) => {
    setActionLoading(true)
    setActionMessage(null)
    const toFulfill = quantity !== undefined && quantity > 0 ? quantity : (customFulfillQty > 0 ? customFulfillQty : req.allocated_quantity)
    try {
      const res = await api.fulfillShelterRequest({
        request_id: req.id,
        fulfilled_quantity: toFulfill,
      })
      setActionMessage({
        text: `Fulfilled delivery of ${toFulfill} units to ${req.shelter_name}. Request status: ${res.request.status}`,
        type: 'success',
      })
      setActiveFulfillReq(null)
      loadData()
    } catch (err: any) {
      setActionMessage({
        text: err?.message || 'Fulfillment failed. Cannot fulfill more than allocated units.',
        type: 'error',
      })
    } finally {
      setActionLoading(false)
    }
  }

  // Re-run tactical resource knapsack optimizer
  const handleRerunTactical = async () => {
    setTacticalLoading(true)
    try {
      const res = await api.allocateResources({
        rescue_teams: tacticalRescueTeams,
        medical_teams: tacticalMedicalUnits,
        relief_units: tacticalReliefSupplies,
        emergency_vehicles: tacticalVehicles,
      })
      setFieldAlloc(res)
      setActionMessage({
        text: 'Tactical field knapsack re-optimized across eligible flood-risk zones.',
        type: 'success',
      })
    } catch (err: any) {
      setActionMessage({
        text: err?.message || 'Failed to re-optimize tactical resource distribution.',
        type: 'error',
      })
    } finally {
      setTacticalLoading(false)
    }
  }

  if (loading) return <LoadingState label="Loading central warehouse inventory and fulfillment demand..." />

  return (
    <div className="flex flex-col gap-8 page-enter">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-mono text-amber-400 mb-1">
          <span>SECTION 05</span>
          <span>/</span>
          <span>INVENTORY, ALLOCATION &amp; FULFILLMENT</span>
        </div>
        <h1 className="font-display text-2xl sm:text-3xl text-ink-100 font-bold tracking-tight">
          Resource Planning &amp; Fulfillment
        </h1>
        <p className="text-ink-400 text-sm mt-1 max-w-3xl leading-relaxed">
          Central logistics command reviewing real shelter resource requests against physical warehouse stock.
          Enforces finite stock limits, prevents duplicate allocations, flags supply deficits, and records immutable fulfillment history.
        </p>

        {studyArea && (
          <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-base-900 border border-base-700 text-xs text-ink-300">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span>Operational Logistics Corridor:</span>
            <strong className="text-ink-100 font-semibold">{studyArea.name}</strong>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-500/30">
              Persistent Storage Active
            </span>
          </div>
        )}
      </div>

      {actionMessage && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex items-center justify-between ${
            actionMessage.type === 'success'
              ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300'
              : 'bg-red-950/40 border-red-500/50 text-red-300'
          }`}
        >
          <div className="flex items-center gap-2">
            <span>{actionMessage.type === 'success' ? '✓' : '⚠️'}</span>
            <span>{actionMessage.text}</span>
          </div>
          <button
            onClick={() => setActionMessage(null)}
            className="text-ink-400 hover:text-ink-100 font-mono text-xs ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Summary KPI Cards */}
      {demandSummary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <StatCard
            label="Total Shelter Requests"
            value={demandSummary.total_requests}
            sublabel="Direct from operational shelters"
            accent="teal"
          />
          <StatCard
            label="Fulfilled Requests"
            value={demandSummary.fulfilled_requests}
            sublabel={`${demandSummary.pending_requests} pending allocation`}
            accent="low"
          />
          <StatCard
            label="Tracked Commodities"
            value={inventory.length}
            sublabel="Central stock ledger"
            accent="moderate"
          />
          <StatCard
            label="Inventory Guardrail"
            value="Active"
            sublabel="Prevents over-allocation & duplicates"
            accent="low"
          />
        </div>
      )}

      {/* Warehouse Inventory Stock Status */}
      <div className="panel p-6 border-base-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-base-700/60 pb-3 mb-4 gap-2">
          <div>
            <span className="eyebrow">Warehouse Ledger</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Central Disaster Relief Stock Levels
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Current real-time balances in central distribution warehouses. Allocations directly deduct available units.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-amber-400 border border-base-700">
            FINITE STOCK LIMITS ENFORCED
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {inventory.map((item) => {
            const pctAllocated = (item.allocated / (item.total_stock || 1)) * 100
            return (
              <div
                key={item.item}
                className="p-4 rounded-lg bg-base-850 border border-base-750 flex flex-col justify-between"
              >
                <div>
                  <span className="text-[10px] font-mono text-ink-500 uppercase">{item.category}</span>
                  <h4 className="font-display font-semibold text-xs text-ink-100 mt-0.5 leading-snug">
                    {item.item}
                  </h4>
                  <div className="mt-3 flex items-baseline justify-between">
                    <span className="text-xl font-mono font-bold text-signal-teal">
                      {item.available.toLocaleString()}
                    </span>
                    <span className="text-[10px] text-ink-500 font-mono">/ {item.total_stock.toLocaleString()} {item.unit}</span>
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-base-750">
                  <div className="flex justify-between text-[10px] text-ink-400 font-mono mb-1">
                    <span>Allocated:</span>
                    <span>{pctAllocated.toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-base-950 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-amber-400 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, pctAllocated)}%` }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Demand & Shortage Analysis Matrix */}
      {demandSummary && (
        <div className="panel p-6 border-base-700">
          <div className="border-b border-base-700/60 pb-3 mb-4">
            <span className="eyebrow">Shortage Identification Matrix</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Shelter Demand vs Available Warehouse Stock
            </h3>
            <p className="text-ink-400 text-xs mt-0.5">
              Identifies unmet emergency shelter requirements before physical truck dispatch. Shortages require replenishment orders.
            </p>
          </div>

          <div className="responsive-table-container">
            <table className="w-full text-left text-xs text-ink-300 min-w-[650px]">
              <thead className="bg-base-800 font-mono text-[11px] text-ink-400 uppercase border-b border-base-700">
                <tr>
                  <th className="py-2.5 px-3">Resource Commodity</th>
                  <th className="py-2.5 px-3">Gross Demand</th>
                  <th className="py-2.5 px-3">Allocated</th>
                  <th className="py-2.5 px-3">Fulfilled / Delivered</th>
                  <th className="py-2.5 px-3">Available Stock</th>
                  <th className="py-2.5 px-3">Shortage Alert</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-base-800">
                {demandSummary.demand_by_resource.map((d) => {
                  const hasShortage = d.shortage > 0
                  return (
                    <tr key={d.resource_type} className="hover:bg-base-800/40">
                      <td className="py-2.5 px-3 font-medium text-ink-100">{d.resource_type}</td>
                      <td className="py-2.5 px-3 font-mono font-bold">{d.requested.toLocaleString()} {d.unit}</td>
                      <td className="py-2.5 px-3 font-mono text-purple-300">{d.allocated.toLocaleString()} {d.unit}</td>
                      <td className="py-2.5 px-3 font-mono text-emerald-400">{d.fulfilled.toLocaleString()} {d.unit}</td>
                      <td className="py-2.5 px-3 font-mono text-signal-teal">{d.available_stock.toLocaleString()} {d.unit}</td>
                      <td className="py-2.5 px-3">
                        {hasShortage ? (
                          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-500/40">
                            DEFICIT: {d.shortage.toLocaleString()} {d.unit}
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/30">
                            COVERED
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Hybrid Quantum Resource Knapsack Allocation (Milestone 4) */}
      <div className="panel p-6 border-signal-blueDim/40">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-base-750 pb-3 mb-4 gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-signal-blue" />
              <span className="eyebrow text-signal-blue">Combinatorial Knapsack Optimization</span>
            </div>
            <h3 className="font-display text-lg text-ink-100 font-semibold mt-0.5">
              Hybrid Quantum Shelter Resource Knapsack Allocation (QAOA)
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Encodes scarce supply distribution into an Ising/QUBO knapsack. Balances request urgency with proportional equity while guaranteeing zero inventory over-allocation.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-signal-blue border border-signal-blue/30 self-start sm:self-auto">
            QAOA DISCRETE KNAPSACK
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
          <div className="p-3 bg-base-850 rounded border border-base-750 sm:col-span-2">
            <label className="text-[10px] font-mono text-ink-400 uppercase block mb-1">
              Resource Commodity to Optimize
            </label>
            <select
              value={quantumResourceTarget}
              onChange={(e) => setQuantumResourceTarget(e.target.value)}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1.5 text-xs text-ink-100 font-mono w-full focus:outline-none focus:border-signal-blue"
            >
              {inventory.map((i) => (
                <option key={i.item} value={i.item}>
                  {i.item} (Available Stock: {i.available} {i.unit})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleRunQuantumAlloc}
              disabled={quantumAllocLoading || requests.length === 0}
              className="w-full bg-signal-blue/20 hover:bg-signal-blue/30 text-signal-blue border border-signal-blue/40 text-xs font-semibold py-2.5 px-4 rounded-lg transition-colors disabled:opacity-40 min-h-[44px] flex items-center justify-center"
            >
              {quantumAllocLoading ? 'Simulating QAOA Knapsack…' : 'Run Quantum Resource Optimizer'}
            </button>
          </div>
        </div>

        {quantumAllocError && (
          <div className="p-3 rounded-lg bg-red-950/40 border border-red-500/40 text-red-300 text-xs mb-4">
            {quantumAllocError}
          </div>
        )}

        {quantumAllocResult && (
          <div className="space-y-4 pt-2">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Available Stock:</span>
                <strong className="text-signal-teal font-mono text-base">
                  {quantumAllocResult.available_stock.toLocaleString()}
                </strong>
                <span className="text-[10px] text-ink-500 block font-mono">
                  Requested: {quantumAllocResult.total_requested.toLocaleString()}
                </span>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">QAOA Allocated:</span>
                <strong className="text-signal-blue font-mono text-base">
                  {quantumAllocResult.total_allocated.toLocaleString()}
                </strong>
                <span className="text-[10px] text-ink-500 block font-mono">
                  Unmet: {quantumAllocResult.unmet_demand.toLocaleString()}
                </span>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Classical Baseline:</span>
                <strong className="text-ink-200 font-mono text-base">
                  {quantumAllocResult.classical_baseline.total_allocated.toLocaleString()}
                </strong>
                <span className="text-[10px] text-ink-500 block font-mono">
                  Greedy Unmet: {quantumAllocResult.classical_baseline.unmet_demand.toLocaleString()}
                </span>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Solver Runtime:</span>
                <strong className="text-ink-200 font-mono text-sm block">
                  Quantum: {quantumAllocResult.solver_metadata.execution_time_ms.toFixed(1)} ms
                </strong>
                <span className="text-[10px] text-ink-500 font-mono">
                  Classical: {quantumAllocResult.classical_baseline.execution_time_ms.toFixed(1)} ms
                </span>
              </div>
            </div>

            {/* Allocations breakdown */}
            <div className="responsive-table-container rounded-lg border border-base-750">
              <table className="w-full text-left text-xs text-ink-300 min-w-[560px]">
                <thead className="bg-base-800 font-mono text-[11px] text-ink-400 uppercase border-b border-base-700">
                  <tr>
                    <th className="py-2 px-3">Req ID</th>
                    <th className="py-2 px-3">Shelter</th>
                    <th className="py-2 px-3">Urgency</th>
                    <th className="py-2 px-3">Requested</th>
                    <th className="py-2 px-3">QAOA Allocated</th>
                    <th className="py-2 px-3">Fulfillment %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-base-800 bg-base-900">
                  {quantumAllocResult.allocations.map((a) => (
                    <tr key={a.request_id} className="hover:bg-base-850">
                      <td className="py-2 px-3 font-mono font-semibold text-ink-100">{a.request_id}</td>
                      <td className="py-2 px-3 font-medium text-ink-200">{a.shelter_name}</td>
                      <td className="py-2 px-3">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${URGENCY_BADGES[a.urgency] || URGENCY_BADGES.MODERATE}`}>
                          {a.urgency}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono">{a.requested_quantity.toLocaleString()}</td>
                      <td className="py-2 px-3 font-mono font-bold text-signal-blue">
                        {a.allocated_quantity.toLocaleString()}
                      </td>
                      <td className="py-2 px-3 font-mono">
                        {(a.fraction_allocated * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
              <div className="text-[11px] font-mono text-ink-400">
                Guaranteed Conservation: Total Allocated ({quantumAllocResult.total_allocated}) ≤ Available Stock ({quantumAllocResult.available_stock})
              </div>
              <button
                onClick={handleApplyQuantumAlloc}
                disabled={quantumApplyLoading || quantumAllocResult.allocations.length === 0}
                className="bg-emerald-600 hover:bg-emerald-500 text-base-950 font-bold text-xs py-2.5 px-4 rounded-lg transition-colors disabled:opacity-40 self-end sm:self-auto min-h-[40px] flex items-center justify-center"
              >
                {quantumApplyLoading ? 'Applying to Ledger…' : 'Apply Quantum Allocations to Ledger'}
              </button>
            </div>

            {/* Provenance Footer */}
            <div className="p-3 rounded-lg bg-base-950 border border-base-800 text-[11px] font-mono text-ink-400 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-signal-blue font-bold">QAOA KNAPSACK PROVENANCE:</span>
                <span>Backend: <strong className="text-ink-200">{quantumAllocResult.solver_metadata.backend}</strong></span>
                <span>• Qubits: <strong className="text-ink-200">{quantumAllocResult.solver_metadata.num_qubits}</strong></span>
                <span>• Depth: <strong className="text-ink-200">{quantumAllocResult.solver_metadata.circuit_depth}</strong></span>
                <span>• Shots: <strong className="text-ink-200">{quantumAllocResult.solver_metadata.shots}</strong></span>
              </div>
              <span className="text-[10px] text-ink-500">
                Inventory bounds enforced via quadratic penalty function and classical verification guard.
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Operator Shelter Requests & Interactive Allocation */}
      <div className="panel p-6 border-base-700">
        <div className="border-b border-base-700/60 pb-3 mb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <span className="eyebrow">Dispatch Console</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Review, Prioritize &amp; Allocate Shelter Requests
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Review requests lodged from operational shelters. Check available stock before allocating.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-ink-400">{requests.length} Requests on Ledger</span>
            <button
              onClick={loadData}
              className="text-xs font-mono text-signal-teal hover:underline"
            >
              Sync Records
            </button>
          </div>
        </div>

        {requests.length === 0 ? (
          <div className="p-8 text-center bg-base-850/60 rounded-lg border border-base-750">
            <p className="text-xs text-ink-400 font-mono">
              No active shelter resource requests lodged yet. Submit a request from the &quot;Safe Shelters &amp; Shelter Requests&quot; section to begin allocation.
            </p>
          </div>
        ) : (
          <div className="responsive-table-container">
            <table className="w-full text-left text-xs text-ink-300 min-w-[760px]">
              <thead className="bg-base-800 font-mono text-[11px] text-ink-400 uppercase border-b border-base-700">
                <tr>
                  <th className="py-2.5 px-3">Req ID</th>
                  <th className="py-2.5 px-3">Shelter Facility</th>
                  <th className="py-2.5 px-3">Resource Type</th>
                  <th className="py-2.5 px-3">Requested</th>
                  <th className="py-2.5 px-3">In Stock</th>
                  <th className="py-2.5 px-3">Allocated</th>
                  <th className="py-2.5 px-3">Fulfilled</th>
                  <th className="py-2.5 px-3">Urgency</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-base-800">
                {requests.map((r) => {
                  const invItem = getInventoryForItem(r.resource_type)
                  const availableStock = invItem ? invItem.available : 0
                  const hasDeficit = availableStock < r.requested_quantity && r.status === 'PENDING'
                  const isAllocModalOpen = activeAllocReq?.id === r.id
                  const isFulfillModalOpen = activeFulfillReq?.id === r.id

                  return (
                    <tr key={r.id} className="hover:bg-base-800/40">
                      <td className="py-2.5 px-3 font-mono font-semibold text-ink-100">{r.id}</td>
                      <td className="py-2.5 px-3 font-medium text-ink-200">
                        {r.shelter_name}
                        {r.notes && <div className="text-[10px] text-ink-500 truncate max-w-[150px]">{r.notes}</div>}
                      </td>
                      <td className="py-2.5 px-3">{r.resource_type}</td>
                      <td className="py-2.5 px-3 font-mono font-bold text-ink-100">{r.requested_quantity.toLocaleString()}</td>
                      <td className="py-2.5 px-3 font-mono">
                        <span className={hasDeficit ? 'text-red-400 font-semibold' : 'text-signal-teal'}>
                          {availableStock.toLocaleString()}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-purple-300">{r.allocated_quantity.toLocaleString()}</td>
                      <td className="py-2.5 px-3 font-mono text-emerald-400">{r.fulfilled_quantity.toLocaleString()}</td>
                      <td className="py-2.5 px-3">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${URGENCY_BADGES[r.urgency] || URGENCY_BADGES.MODERATE}`}>
                          {r.urgency}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${STATUS_BADGES[r.status] || STATUS_BADGES.PENDING}`}>
                          {r.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {r.status !== 'FULFILLED' ? (
                          <div className="inline-flex items-center gap-1.5 justify-end">
                            {r.status === 'PENDING' && (
                              <button
                                onClick={() => {
                                  setActiveAllocReq(r)
                                  setCustomAllocQty(Math.min(r.requested_quantity, availableStock))
                                }}
                                disabled={actionLoading}
                                className="px-3 py-1.5 rounded bg-amber-500 hover:bg-amber-400 text-base-950 text-[11px] font-semibold transition-colors disabled:opacity-40 min-h-[34px] flex items-center justify-center"
                              >
                                Allocate
                              </button>
                            )}
                            {(r.status === 'ALLOCATED' || r.status === 'PARTIALLY_ALLOCATED' || r.status === 'PARTIALLY_FULFILLED') && (
                              <button
                                onClick={() => {
                                  setActiveFulfillReq(r)
                                  setCustomFulfillQty(r.allocated_quantity)
                                }}
                                disabled={actionLoading || r.allocated_quantity <= 0}
                                className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-base-950 text-[11px] font-semibold transition-colors disabled:opacity-40 min-h-[34px] flex items-center justify-center"
                              >
                                Fulfill
                              </button>
                            )}
                          </div>
                        ) : (
                          <span className="text-[10px] font-mono text-emerald-400">Completed ✓</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Interactive Allocation Modal / Form */}
      {activeAllocReq && (
        <div className="panel p-5 border-amber-500/40 bg-base-900 rounded-xl">
          <div className="flex items-center justify-between border-b border-base-750 pb-3">
            <div>
              <span className="text-[10px] font-mono text-amber-400 uppercase font-semibold">Stock Allocation Action</span>
              <h4 className="font-display text-base font-bold text-ink-100 mt-0.5">
                Allocate Stock to Request {activeAllocReq.id} ({activeAllocReq.shelter_name})
              </h4>
            </div>
            <button onClick={() => setActiveAllocReq(null)} className="text-ink-400 hover:text-ink-100 text-xs font-mono">
              ✕ Cancel
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4 text-xs">
            <div className="p-3 bg-base-850 rounded border border-base-750">
              <span className="text-ink-500 font-mono block">Commodity:</span>
              <strong className="text-ink-100 mt-1 block">{activeAllocReq.resource_type}</strong>
            </div>
            <div className="p-3 bg-base-850 rounded border border-base-750">
              <span className="text-ink-500 font-mono block">Requested Quantity:</span>
              <strong className="text-amber-400 font-mono mt-1 block text-sm">{activeAllocReq.requested_quantity} units</strong>
            </div>
            <div className="p-3 bg-base-850 rounded border border-base-750">
              <span className="text-ink-500 font-mono block">Available Warehouse Stock:</span>
              <strong className="text-signal-teal font-mono mt-1 block text-sm">
                {getInventoryForItem(activeAllocReq.resource_type)?.available ?? 0} units
              </strong>
            </div>
          </div>

          <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-base-750">
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs font-mono text-ink-300">Quantity to Allocate:</label>
              <input
                type="number"
                min={1}
                max={getInventoryForItem(activeAllocReq.resource_type)?.available ?? activeAllocReq.requested_quantity}
                value={customAllocQty}
                onChange={(e) => setCustomAllocQty(Number(e.target.value))}
                className="bg-base-950 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 font-mono w-32 focus:outline-none focus:border-amber-400 min-h-[38px]"
              />
              <button
                type="button"
                onClick={() => setCustomAllocQty(Math.min(activeAllocReq.requested_quantity, getInventoryForItem(activeAllocReq.resource_type)?.available ?? 0))}
                className="text-[11px] text-signal-cyan underline font-mono py-1"
              >
                Max Available
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveAllocReq(null)}
                className="px-3.5 py-2 rounded bg-base-800 text-ink-300 text-xs font-medium min-h-[38px]"
              >
                Cancel
              </button>
              <button
                onClick={() => handleAllocate(activeAllocReq, customAllocQty)}
                disabled={actionLoading || customAllocQty <= 0}
                className="px-4 py-2 rounded bg-amber-500 hover:bg-amber-400 text-base-950 text-xs font-bold transition-colors disabled:opacity-40 min-h-[38px] flex items-center justify-center"
              >
                {actionLoading ? 'Allocating…' : 'Confirm Allocation'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Fulfillment Modal / Form */}
      {activeFulfillReq && (
        <div className="panel p-5 border-emerald-500/40 bg-base-900 rounded-xl">
          <div className="flex items-center justify-between border-b border-base-750 pb-3">
            <div>
              <span className="text-[10px] font-mono text-emerald-400 uppercase font-semibold">Physical Dispatch Confirmation</span>
              <h4 className="font-display text-base font-bold text-ink-100 mt-0.5">
                Confirm Delivery Fulfillment for {activeFulfillReq.id} ({activeFulfillReq.shelter_name})
              </h4>
            </div>
            <button onClick={() => setActiveFulfillReq(null)} className="text-ink-400 hover:text-ink-100 text-xs font-mono">
              ✕ Cancel
            </button>
          </div>

          <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs font-mono text-ink-300">Quantity Delivered:</label>
              <input
                type="number"
                min={1}
                max={activeFulfillReq.allocated_quantity}
                value={customFulfillQty}
                onChange={(e) => setCustomFulfillQty(Number(e.target.value))}
                className="bg-base-950 border border-base-700 rounded px-3 py-2 text-xs text-ink-100 font-mono w-32 focus:outline-none focus:border-emerald-400 min-h-[38px]"
              />
              <span className="text-[11px] text-ink-500 font-mono">
                Allocated balance: {activeFulfillReq.allocated_quantity} units
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveFulfillReq(null)}
                className="px-3.5 py-2 rounded bg-base-800 text-ink-300 text-xs font-medium min-h-[38px]"
              >
                Cancel
              </button>
              <button
                onClick={() => handleFulfill(activeFulfillReq, customFulfillQty)}
                disabled={actionLoading || customFulfillQty <= 0}
                className="px-4 py-2 rounded bg-emerald-500 hover:bg-emerald-400 text-base-950 text-xs font-bold transition-colors disabled:opacity-40 min-h-[38px] flex items-center justify-center"
              >
                {actionLoading ? 'Recording Dispatch…' : 'Record Verified Fulfillment'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Part C: Tactical Field Resource Knapsack Optimizer */}
      <div className="panel p-6 border-base-700">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-base-700/60 pb-3 mb-4 gap-2">
          <div>
            <span className="eyebrow text-signal-cyan">Tactical Field Dispatch Optimizer</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Zone Risk Knapsack Resource Allocation
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Reuses the tactical integer programming optimization engine to distribute mobile response teams across flood-risk zones.
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-base-800 text-signal-cyan border border-base-700">
            INTEGER KNAPSACK ALGORITHM
          </span>
        </div>

        {/* Input Parameters & Re-run */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-500 uppercase block mb-1">Rescue Teams</label>
            <input
              type="number"
              min={1}
              max={50}
              value={tacticalRescueTeams}
              onChange={(e) => setTacticalRescueTeams(Number(e.target.value))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>
          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-500 uppercase block mb-1">Medical Teams</label>
            <input
              type="number"
              min={1}
              max={50}
              value={tacticalMedicalUnits}
              onChange={(e) => setTacticalMedicalUnits(Number(e.target.value))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>
          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-500 uppercase block mb-1">Relief Units</label>
            <input
              type="number"
              min={1}
              max={100}
              value={tacticalReliefSupplies}
              onChange={(e) => setTacticalReliefSupplies(Number(e.target.value))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>
          <div className="p-3 bg-base-850 rounded border border-base-750">
            <label className="text-[10px] font-mono text-ink-500 uppercase block mb-1">Emergency Vehicles</label>
            <input
              type="number"
              min={1}
              max={50}
              value={tacticalVehicles}
              onChange={(e) => setTacticalVehicles(Number(e.target.value))}
              className="bg-base-950 border border-base-700 rounded px-2.5 py-1 text-xs text-ink-100 font-mono w-full"
            />
          </div>
        </div>

        <button
          onClick={handleRerunTactical}
          disabled={tacticalLoading}
          className="bg-base-800 hover:bg-base-750 text-signal-cyan border border-base-700 text-xs font-semibold py-2.5 px-4 rounded transition-colors disabled:opacity-40 min-h-[44px] flex items-center justify-center"
        >
          {tacticalLoading ? 'Optimizing Knapsack…' : 'Re-Run Tactical Resource Optimizer'}
        </button>

        {/* Tactical Output */}
        {fieldAlloc && (
          <div className="mt-5 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Eligible Zones:</span>
                <strong className="text-ink-100 font-mono text-base">{fieldAlloc.summary.eligible_zones_count}</strong>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Zones Serviced:</span>
                <strong className="text-signal-teal font-mono text-base">{fieldAlloc.summary.zones_serviced_count}</strong>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Rescue Team Exhaustion:</span>
                <strong className="text-amber-400 font-mono text-base">
                  {fieldAlloc.summary.budget_exhaustion_pct?.rescue_teams?.toFixed(0) ?? 100}%
                </strong>
              </div>
              <div className="p-3 bg-base-900 rounded border border-base-750">
                <span className="text-ink-500 font-mono block">Algorithm Formulation:</span>
                <strong className="text-ink-200 text-xs truncate block">{fieldAlloc.mathematical_formulation?.objective || 'Maximum Weighted Coverage'}</strong>
              </div>
            </div>

            {/* Serviced Zones Table */}
            <div className="responsive-table-container">
              <table className="w-full text-left text-xs text-ink-300 min-w-[620px]">
                <thead className="bg-base-800 font-mono text-[11px] text-ink-400 uppercase border-b border-base-700">
                  <tr>
                    <th className="py-2.5 px-3">Zone ID</th>
                    <th className="py-2.5 px-3">Risk Level</th>
                    <th className="py-2.5 px-3">River Standoff</th>
                    <th className="py-2.5 px-3">Priority Score</th>
                    <th className="py-2.5 px-3">Allocated Tactical Units</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-base-800">
                  {fieldAlloc.allocations.slice(0, 8).map((a) => (
                    <tr key={a.zone_id} className="hover:bg-base-800/40">
                      <td className="py-2 px-3 font-mono font-semibold text-ink-100">{a.zone_id}</td>
                      <td className="py-2 px-3">
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                          a.risk_level === 'CRITICAL' ? 'bg-red-950 text-red-300 border border-red-500/40' : 'bg-amber-950 text-amber-300 border border-amber-500/40'
                        }`}>
                          {a.risk_level}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono">{a.distance_to_river_km.toFixed(2)} km</td>
                      <td className="py-2 px-3 font-mono font-semibold text-signal-teal">{a.priority_score.toFixed(2)}</td>
                      <td className="py-2 px-3 font-mono text-ink-200">
                        {Object.entries(a.allocated_resources)
                          .filter(([_, q]) => q > 0)
                          .map(([name, q]) => `${name.replace('_', ' ')}: ${q}`)
                          .join(', ') || 'Standby'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Chronological Audit Log */}
      <div className="panel p-6 border-base-700">
        <div className="border-b border-base-700/60 pb-3 mb-4 flex items-center justify-between">
          <div>
            <span className="eyebrow">Traceability Ledger</span>
            <h3 className="font-display text-lg text-ink-100 font-semibold">
              Allocation &amp; Dispatch Audit Trail
            </h3>
            <p className="text-xs text-ink-400 mt-0.5">
              Chronological log of supply commitments and verified deliveries.
            </p>
          </div>
          <span className="text-xs font-mono text-ink-400">Immutable Event Sequence</span>
        </div>

        <div className="space-y-2">
          {auditLog.map((log, idx) => (
            <div
              key={`${log.timestamp}-${idx}`}
              className="p-3 rounded-lg bg-base-850 border border-base-750 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
            >
              <div className="flex items-center gap-2.5">
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-base-900 border border-base-700 text-signal-teal font-semibold">
                  {log.action}
                </span>
                <span className="text-ink-200 font-medium">{log.details}</span>
              </div>
              <div className="flex items-center gap-3 text-[11px] font-mono text-ink-500 shrink-0">
                <span>By: {log.actor}</span>
                <span>•</span>
                <span>{new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
