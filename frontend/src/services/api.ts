import type {
  DatasetSummary, HydroRecord, ForecastTrainResult, ForecastPrediction, ForecastResults,
  RiskMap, MapLayers, OptimizationRunResponse, ConnectivityResult, CoverageSummary,
  RecommendationsResponse, DashboardSummary, StudyArea, Candidate, DataProvenance,
  RealFloodEvent, ExperimentRunRecord, QuantumOptimizationResponse, OptimizationComparisonResponse,
  QmlForecastResult, ForecastComparisonResponse,
  ShelterRequest, ShelterRequestCreatePayload, InventoryItem, DemandSummaryResponse, AuditLogEntry,
  ShelterPortfolioQuantumResponse, QuantumResourceAllocationResponse,
} from '../types'
const envBase = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '')
const BASE = envBase
  ? (envBase.endsWith('/api') ? envBase : `${envBase}/api`)
  : '/api'

if (import.meta.env.PROD && !envBase) {
  console.warn(
    '[QuantumFlood AI] VITE_API_BASE_URL is not set in production. ' +
    'API calls to /api will resolve to the frontend host unless routed by a reverse proxy. ' +
    'Configure VITE_API_BASE_URL in your hosting provider settings (e.g. Vercel Project Settings).'
  )
}

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  const contentType = res.headers.get('content-type') || ''
  if (contentType.includes('text/html')) {
    throw new ApiError(
      502,
      'Backend returned HTML instead of JSON. Ensure VITE_API_BASE_URL points to the live FastAPI backend rather than the static frontend host.'
    )
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail)
  }
  return res.json()
}

function getStoredStudyArea(): StudyArea | null {
  try {
    const raw = sessionStorage.getItem('qf_active_study_area')
    if (raw) return JSON.parse(raw)
  } catch {}
  return null
}

function setStoredStudyArea(area: StudyArea | null) {
  try {
    if (area) {
      sessionStorage.setItem('qf_active_study_area', JSON.stringify(area))
    } else {
      sessionStorage.removeItem('qf_active_study_area')
    }
  } catch {}
}

function getStoredAnalysisId(): string | null {
  try {
    return sessionStorage.getItem('qf_active_analysis_id')
  } catch {}
  return null
}

function setStoredAnalysisId(id: string | null) {
  try {
    if (id) {
      sessionStorage.setItem('qf_active_analysis_id', id)
    } else {
      sessionStorage.removeItem('qf_active_analysis_id')
    }
  } catch {}
}

export const api = {
  health: () => request<{ status: string; system: string; phase: string }>('/health'),
  regions: () => request<{ regions: StudyArea[] }>('/regions'),

  // Study Area Selection & Geocoding
  selectArea: async (payload: { location_query?: string; latitude?: number; longitude?: number; half_size_deg?: number; study_area?: any }) => {
    const res = await request<import('../types').AreaSelectResult>('/area/select', { method: 'POST', body: JSON.stringify(payload) })
    if (res.status === 'OK' && res.study_area) {
      setStoredStudyArea(res.study_area)
    }
    return res
  },
  resetArea: async () => {
    const res = await request<{ status: string; message: string; study_area: StudyArea; data_availability: any }>('/area/reset', { method: 'POST' })
    if (res.status === 'OK' && res.study_area) {
      setStoredStudyArea(res.study_area)
    }
    setStoredAnalysisId(null)
    return res
  },
  currentArea: async () => {
    const stored = getStoredStudyArea()
    const res = await request<{ is_default_location: boolean; study_area: StudyArea; data_availability: any }>('/area/current')
    if (stored) {
      return {
        ...res,
        is_default_location: Boolean(stored.name?.includes('Vijayawada')),
        study_area: stored,
      }
    }
    return res
  },
  searchLocations: (query: string, limit = 5) =>
    request<{ results: import('../types').LocationSearchResult[] }>(`/area/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  datasetSummary: () => request<DatasetSummary>('/data/summary'),
  timeseries: (limit = 180) => request<{ records: HydroRecord[] }>(`/data/timeseries?limit=${limit}`),
  dataTimeseries: (limit = 180) => request<{ records: HydroRecord[] }>(`/data/timeseries?limit=${limit}`),
  historicalEvents: () => request<{ events: any[] }>('/data/historical-events'),
  historicalEventsReal: () => request<{ events: RealFloodEvent[] }>('/data/historical-events-real'),
  dataProvenance: () => request<DataProvenance>('/data/provenance'),
  datasetRegistry: () => request<{ datasets: { id: string; name: string; mode: string; description: string }[] }>('/datasets'),

  trainForecast: (horizon_days: number) =>
    request<ForecastTrainResult>('/forecast/train', { method: 'POST', body: JSON.stringify({ horizon_days }) }),
  predictForecast: (horizon_days: number) =>
    request<ForecastPrediction>('/forecast/predict', { method: 'POST', body: JSON.stringify({ horizon_days, study_area: getStoredStudyArea() }) }),
  forecastResults: () => request<ForecastResults>('/forecast/results'),

  trainQmlForecast: (payload: { horizon_days?: number; n_layers?: number; max_iter?: number; train_subsample?: number; seed?: number }) =>
    request<QmlForecastResult>('/forecast/qml/train', { method: 'POST', body: JSON.stringify(payload) }),
  predictQmlForecast: (horizon_days: number) =>
    request<ForecastPrediction>('/forecast/qml/predict', { method: 'POST', body: JSON.stringify({ horizon_days, study_area: getStoredStudyArea() }) }),
  qmlForecastResults: () => request<QmlForecastResult>('/forecast/qml/results'),
  compareForecasts: (horizon_days: number) =>
    request<ForecastComparisonResponse>('/forecast/compare', { method: 'POST', body: JSON.stringify({ horizon_days, study_area: getStoredStudyArea() }) }),

  generateRisk: async (payload: { water_level_m?: number; inflow_ktcmd?: number; rainfall_mm_24h?: number; use_latest_forecast?: boolean; resolution?: string; forecast_model_preference?: string; study_area?: any; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    const res = await request<RiskMap>('/risk/generate', { method: 'POST', body: JSON.stringify(body) })
    if (res.analysis_id) {
      setStoredAnalysisId(res.analysis_id)
    }
    return res
  },
  riskZones: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as unknown as RiskMap)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<RiskMap>(`/risk/zones${query}`)
  },

  mapLayers: (area?: StudyArea | null) => {
    const a = area || getStoredStudyArea()
    const query = a?.center?.lat !== undefined && a?.center?.lon !== undefined
      ? `?lat=${a.center.lat}&lon=${a.center.lon}&name=${encodeURIComponent(a.name || '')}`
      : ''
    return request<MapLayers>(`/map/layers${query}`)
  },

  runOptimization: async (payload: { num_sensors: number; coverage_radius_km: number; comm_range_km: number; max_comm_nodes: number; study_area?: any; zones?: any[]; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    const res = await request<OptimizationRunResponse>('/optimization/run', { method: 'POST', body: JSON.stringify(body) })
    if (res.analysis_id) {
      setStoredAnalysisId(res.analysis_id)
    }
    return res
  },
  runQuantumOptimization: async (payload: {
    num_sensors: number
    coverage_radius_km: number
    p?: number
    shots?: number
    seed?: number
    formulation_mode?: string
    max_candidates?: number
    study_area?: any
    zones?: any[]
    analysis_id?: string
  }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    const res = await request<QuantumOptimizationResponse>('/optimization/quantum', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    if (res.analysis_id) {
      setStoredAnalysisId(res.analysis_id)
    }
    return res
  },
  compareOptimization: (payload: {
    num_sensors: number
    coverage_radius_km: number
    p?: number
    shots?: number
    seed?: number
    max_candidates?: number
    study_area?: any
    zones?: any[]
  }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      ...payload,
    }
    return request<OptimizationComparisonResponse>('/optimization/compare', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  candidates: (area?: StudyArea) => {
    const a = area || getStoredStudyArea()
    const query = a?.center?.lat !== undefined && a?.center?.lon !== undefined ? `?lat=${a.center.lat}&lon=${a.center.lon}` : ''
    return request<{ candidates: Candidate[]; count: number }>(`/optimization/candidates${query}`)
  },
  latestOptimization: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<{ optimization: any; connectivity: any; params: any }>(`/optimization/results${query}`)
  },
  optimizationResults: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<{ optimization: any; connectivity: any; params: any }>(`/optimization/results${query}`)
  },

  networkResults: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<ConnectivityResult>(`/network/results${query}`)
  },
  coverageAnalysis: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<CoverageSummary>(`/coverage/analysis${query}`)
  },

  recommendations: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as unknown as RecommendationsResponse)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<RecommendationsResponse>(`/recommendations${query}`)
  },

  dashboardSummary: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    const query = aid ? `?analysis_id=${encodeURIComponent(aid)}` : ''
    return request<DashboardSummary>(`/dashboard/summary${query}`)
  },

  runExperiments: (payload?: { resolution?: string; study_area?: any; analysis_id?: string }) => {
    const body = {
      study_area: payload?.study_area || getStoredStudyArea(),
      analysis_id: payload?.analysis_id || getStoredAnalysisId() || undefined,
      ...(payload ?? {}),
    }
    return request<ExperimentRunRecord>('/optimization/experiments/run', { method: 'POST', body: JSON.stringify(body) })
  },
  listExperimentRuns: () => request<{ runs: string[] }>('/optimization/experiments/results'),
  getExperimentRun: (filename: string) => request<ExperimentRunRecord>(`/optimization/experiments/results/${filename}`),

  // Module 1: Safe Locations
  evaluateSafeLocations: (payload: { weight_elevation?: number; weight_risk?: number; weight_distance?: number; weight_accessibility?: number; min_elevation_m?: number; max_risk_level?: string; study_area?: any; zones?: any[]; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<import('../types').SafeLocationEvaluationResponse>('/safe-locations/evaluate', { method: 'POST', body: JSON.stringify(body) })
  },
  candidateFacilities: (area?: StudyArea | null) => {
    const a = area || getStoredStudyArea()
    const query = a?.center?.lat !== undefined && a?.center?.lon !== undefined ? `?lat=${a.center.lat}&lon=${a.center.lon}` : ''
    return request<{ candidates: any[]; count: number }>(`/safe-locations/candidates${query}`)
  },
  latestSafeLocations: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    const query = aid ? `?analysis_id=${encodeURIComponent(aid)}` : ''
    return request<import('../types').SafeLocationEvaluationResponse>(`/safe-locations/latest${query}`)
  },

  // Module 2: Evacuation Routing
  planEvacuationRoute: (payload: { origin_lat: number; origin_lon: number; dest_lat: number; dest_lon: number; origin_name?: string; dest_name?: string; risk_penalty_beta?: number; study_area?: any; zones?: any[]; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<import('../types').EvacuationRouteResponse>('/evacuation/route', { method: 'POST', body: JSON.stringify(body) })
  },
  evacuationRoadNetwork: (area?: StudyArea | null) => {
    const a = area || getStoredStudyArea()
    const query = a?.center?.lat !== undefined && a?.center?.lon !== undefined ? `?lat=${a.center.lat}&lon=${a.center.lon}` : ''
    return request<any>(`/evacuation/network${query}`)
  },
  latestEvacuationRoute: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<import('../types').EvacuationRouteResponse>(`/evacuation/latest${query}`)
  },

  // Module 3: Adaptive Sensor Redeployment
  redeploySensors: (payload: { sensor_budget?: number; coverage_radius_km?: number; resolution?: string; use_active_sensors?: boolean; study_area?: any; zones?: any[]; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<import('../types').AdaptiveRedeploymentResponse>('/sensors/redeploy', { method: 'POST', body: JSON.stringify(body) })
  },
  latestRedeployment: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<import('../types').AdaptiveRedeploymentResponse>(`/sensors/redeploy/latest${query}`)
  },

  // Module 4: Network Resilience
  simulateNetworkResilience: (payload: { failed_node_ids: string[]; comm_range_km?: number; analysis_id?: string }) => {
    const body = {
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<import('../types').NetworkResilienceResponse>('/network/resilience/simulate', { method: 'POST', body: JSON.stringify(body) })
  },
  latestNetworkResilience: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) {
      return Promise.resolve(null as any)
    }
    const query = `?analysis_id=${encodeURIComponent(aid)}`
    return request<import('../types').NetworkResilienceResponse>(`/network/resilience/latest${query}`)
  },

  // Module 5: Emergency Resource Allocation
  allocateResources: (payload: { rescue_teams?: number; medical_teams?: number; relief_units?: number; emergency_vehicles?: number; min_risk_level?: string; study_area?: any; zones?: any[]; analysis_id?: string }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<import('../types').ResourceAllocationResponse>('/resources/allocate', { method: 'POST', body: JSON.stringify(body) })
  },
  latestAllocations: (analysisId?: string) => {
    const aid = analysisId || getStoredAnalysisId()
    const query = aid ? `?analysis_id=${encodeURIComponent(aid)}` : ''
    return request<import('../types').ResourceAllocationResponse>(`/resources/latest${query}`)
  },

  // Module 6: Multi-Scenario Comparison
  scenarioPresets: () => request<{ presets: import('../types').ScenarioDefinition[]; active_scenario_id?: string }>('/scenarios/presets'),
  runSingleScenario: (payload: import('../types').ScenarioDefinition) =>
    request<import('../types').ScenarioRunResult>('/scenarios/run', { method: 'POST', body: JSON.stringify(payload) }),
  compareScenarios: (payload?: { scenarios?: import('../types').ScenarioDefinition[] }) =>
    request<import('../types').ScenarioComparisonResponse>('/scenarios/compare', { method: 'POST', body: JSON.stringify(payload ?? {}) }),
  activateScenario: (payload: { scenario_id: string; custom_params?: any }) =>
    request<import('../types').ScenarioActivationResponse>('/scenarios/activate', { method: 'POST', body: JSON.stringify(payload) }),

  // Reports
  generateReport: (payload?: { analysis_id?: string; format?: 'json' | 'html'; title?: string }) => {
    const aid = payload?.analysis_id || getStoredAnalysisId()
    return request<any>('/reports/generate', {
      method: 'POST',
      body: JSON.stringify({ ...payload, analysis_id: aid }),
    })
  },
  getReport: (analysisId?: string, format: 'json' | 'html' = 'json') => {
    const aid = analysisId || getStoredAnalysisId()
    if (!aid) throw new ApiError(400, 'No active analysis ID for report generation.')
    return request<any>(`/reports/${encodeURIComponent(aid)}?format=${format}`)
  },

  // Section 4: Safe Shelters & Shelter Requests
  listShelterRequests: (shelterId?: string) => {
    const query = shelterId ? `?shelter_id=${encodeURIComponent(shelterId)}` : ''
    return request<{ requests: ShelterRequest[] }>(`/safe-locations/requests${query}`)
  },
  createShelterRequest: (payload: ShelterRequestCreatePayload) => {
    return request<{ status: string; request: ShelterRequest }>('/safe-locations/requests', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  // Section 5: Resource Planning, Inventory & Fulfillment
  getInventory: () => request<{ inventory: InventoryItem[] }>('/resources/inventory'),
  getDemandSummary: () => request<DemandSummaryResponse>('/resources/demand-summary'),
  getAuditLog: () => request<{ audit_trail: AuditLogEntry[] }>('/resources/audit-log'),
  allocateShelterRequest: (payload: { request_id: string; allocated_quantity: number }) => {
    return request<{ status: string; request: ShelterRequest; inventory: InventoryItem }>('/resources/allocate-request', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  fulfillShelterRequest: (payload: { request_id: string; fulfilled_quantity: number }) => {
    return request<{ status: string; request: ShelterRequest }>('/resources/fulfill-request', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  // Hybrid Quantum Shelter Portfolio Optimization
  optimizeShelterPortfolio: (payload: {
    budget: number
    min_separation_km?: number
    p?: number
    shots?: number
    seed?: number
    study_area?: any
    analysis_id?: string
  }) => {
    const body = {
      study_area: payload.study_area || getStoredStudyArea(),
      analysis_id: payload.analysis_id || getStoredAnalysisId() || undefined,
      ...payload,
    }
    return request<ShelterPortfolioQuantumResponse>('/shelters/portfolio/quantum', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  // Hybrid Quantum Resource Knapsack Optimization
  optimizeResourceKnapsack: (payload: {
    resource_type?: string
    p?: number
    shots?: number
    seed?: number
  }) => {
    return request<QuantumResourceAllocationResponse>('/resources/shelter-requests/quantum-optimize', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  // Apply Quantum Allocations
  applyQuantumResourceAllocation: (payload: {
    allocations: Array<{ request_id: string; allocated_quantity: number }>
  }) => {
    return request<{
      status: string
      applied_count: number
      failed_count: number
      applied_allocations: any[]
      failed_allocations: any[]
      audit_records_created: number
    }>('/resources/shelter-requests/quantum-apply', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
}

export { ApiError, getStoredStudyArea, setStoredStudyArea, getStoredAnalysisId, setStoredAnalysisId }
