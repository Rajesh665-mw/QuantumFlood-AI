import type {
  DatasetSummary, HydroRecord, ForecastTrainResult, ForecastPrediction, ForecastResults,
  RiskMap, MapLayers, OptimizationRunResponse, ConnectivityResult, CoverageSummary,
  RecommendationsResponse, DashboardSummary, StudyArea, Candidate, DataProvenance,
  RealFloodEvent, ExperimentRunRecord, QuantumOptimizationResponse, OptimizationComparisonResponse,
  QmlForecastResult, ForecastComparisonResponse,
} from '../types'
const envBase = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '')
const BASE = envBase
  ? (envBase.endsWith('/api') ? envBase : `${envBase}/api`)
  : '/api'
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

export const api = {
  health: () => request<{ status: string; system: string; phase: string }>('/health'),
  regions: () => request<{ regions: StudyArea[] }>('/regions'),

  // Study Area Selection & Geocoding
  selectArea: (payload: { location_query?: string; latitude?: number; longitude?: number; half_size_deg?: number; study_area?: any }) =>
    request<import('../types').AreaSelectResult>('/area/select', { method: 'POST', body: JSON.stringify(payload) }),
  resetArea: () =>
    request<{ status: string; message: string; study_area: StudyArea; data_availability: any }>('/area/reset', { method: 'POST' }),
  currentArea: () =>
    request<{ is_default_location: boolean; study_area: StudyArea; data_availability: any }>('/area/current'),
  searchLocations: (query: string, limit = 5) =>
    request<{ results: import('../types').LocationSearchResult[] }>(`/area/search?query=${encodeURIComponent(query)}&limit=${limit}`),

  datasetSummary: () => request<DatasetSummary>('/data/summary'),
  timeseries: (limit = 180) => request<{ records: HydroRecord[] }>(`/data/timeseries?limit=${limit}`),
  historicalEvents: () => request<{ events: any[] }>('/data/historical-events'),
  historicalEventsReal: () => request<{ events: RealFloodEvent[] }>('/data/historical-events-real'),
  dataProvenance: () => request<DataProvenance>('/data/provenance'),
  datasetRegistry: () => request<{ datasets: { id: string; name: string; mode: string; description: string }[] }>('/datasets'),

  trainForecast: (horizon_days: number) =>
    request<ForecastTrainResult>('/forecast/train', { method: 'POST', body: JSON.stringify({ horizon_days }) }),
  predictForecast: (horizon_days: number) =>
    request<ForecastPrediction>('/forecast/predict', { method: 'POST', body: JSON.stringify({ horizon_days }) }),
  forecastResults: () => request<ForecastResults>('/forecast/results'),

  trainQmlForecast: (payload: { horizon_days?: number; n_layers?: number; max_iter?: number; train_subsample?: number; seed?: number }) =>
    request<QmlForecastResult>('/forecast/qml/train', { method: 'POST', body: JSON.stringify(payload) }),
  predictQmlForecast: (horizon_days: number) =>
    request<ForecastPrediction>('/forecast/qml/predict', { method: 'POST', body: JSON.stringify({ horizon_days }) }),
  qmlForecastResults: () => request<QmlForecastResult>('/forecast/qml/results'),
  compareForecasts: (horizon_days: number) =>
    request<ForecastComparisonResponse>('/forecast/compare', { method: 'POST', body: JSON.stringify({ horizon_days }) }),

  generateRisk: (payload: { water_level_m?: number; inflow_ktcmd?: number; rainfall_mm_24h?: number; use_latest_forecast?: boolean; resolution?: string; forecast_model_preference?: string }) =>
    request<RiskMap>('/risk/generate', { method: 'POST', body: JSON.stringify(payload) }),
  riskZones: () => request<RiskMap>('/risk/zones'),

  mapLayers: () => request<MapLayers>('/map/layers'),

  runOptimization: (payload: { num_sensors: number; coverage_radius_km: number; comm_range_km: number; max_comm_nodes: number }) =>
    request<OptimizationRunResponse>('/optimization/run', { method: 'POST', body: JSON.stringify(payload) }),
  runQuantumOptimization: (payload: {
    num_sensors: number
    coverage_radius_km: number
    p?: number
    shots?: number
    seed?: number
    formulation_mode?: string
    max_candidates?: number
  }) =>
    request<QuantumOptimizationResponse>('/optimization/quantum', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  compareOptimization: (payload: {
    num_sensors: number
    coverage_radius_km: number
    p?: number
    shots?: number
    seed?: number
    max_candidates?: number
  }) =>
    request<OptimizationComparisonResponse>('/optimization/compare', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  candidates: () => request<{ candidates: Candidate[]; count: number }>('/optimization/candidates'),
  optimizationResults: () => request<{ optimization: any; connectivity: any; params: any }>('/optimization/results'),

  networkResults: () => request<ConnectivityResult>('/network/results'),
  coverageAnalysis: () => request<CoverageSummary>('/coverage/analysis'),

  recommendations: () => request<RecommendationsResponse>('/recommendations'),

  dashboardSummary: () => request<DashboardSummary>('/dashboard/summary'),

  runExperiments: (payload?: { resolution?: string }) =>
    request<ExperimentRunRecord>('/optimization/experiments/run', { method: 'POST', body: JSON.stringify(payload ?? {}) }),
  listExperimentRuns: () => request<{ runs: string[] }>('/optimization/experiments/results'),
  getExperimentRun: (filename: string) => request<ExperimentRunRecord>(`/optimization/experiments/results/${filename}`),

  // Module 1: Safe Locations
  evaluateSafeLocations: (payload: { weight_elevation?: number; weight_risk?: number; weight_distance?: number; weight_accessibility?: number; min_elevation_m?: number; max_risk_level?: string }) =>
    request<import('../types').SafeLocationEvaluationResponse>('/safe-locations/evaluate', { method: 'POST', body: JSON.stringify(payload) }),
  candidateFacilities: () => request<{ candidates: any[]; count: number }>('/safe-locations/candidates'),
  latestSafeLocations: () => request<import('../types').SafeLocationEvaluationResponse>('/safe-locations/latest'),

  // Module 2: Evacuation Routing
  planEvacuationRoute: (payload: { origin_lat: number; origin_lon: number; dest_lat: number; dest_lon: number; origin_name?: string; dest_name?: string; risk_penalty_beta?: number }) =>
    request<import('../types').EvacuationRouteResponse>('/evacuation/route', { method: 'POST', body: JSON.stringify(payload) }),
  evacuationRoadNetwork: () => request<any>('/evacuation/network'),
  latestEvacuationRoute: () => request<import('../types').EvacuationRouteResponse>('/evacuation/latest'),

  // Module 3: Adaptive Sensor Redeployment
  redeploySensors: (payload: { sensor_budget?: number; coverage_radius_km?: number; resolution?: string; use_active_sensors?: boolean }) =>
    request<import('../types').AdaptiveRedeploymentResponse>('/sensors/redeploy', { method: 'POST', body: JSON.stringify(payload) }),
  latestRedeployment: () => request<import('../types').AdaptiveRedeploymentResponse>('/sensors/redeploy/latest'),

  // Module 4: Network Resilience
  simulateNetworkResilience: (payload: { failed_node_ids: string[]; comm_range_km?: number }) =>
    request<import('../types').NetworkResilienceResponse>('/network/resilience/simulate', { method: 'POST', body: JSON.stringify(payload) }),
  latestNetworkResilience: () => request<import('../types').NetworkResilienceResponse>('/network/resilience/latest'),

  // Module 5: Emergency Resource Allocation
  allocateResources: (payload: { rescue_teams?: number; medical_teams?: number; relief_units?: number; emergency_vehicles?: number; min_risk_level?: string }) =>
    request<import('../types').ResourceAllocationResponse>('/resources/allocate', { method: 'POST', body: JSON.stringify(payload) }),
  latestAllocations: () => request<import('../types').ResourceAllocationResponse>('/resources/latest'),

  // Module 6: Multi-Scenario Comparison
  scenarioPresets: () => request<{ presets: import('../types').ScenarioDefinition[]; active_scenario_id?: string }>('/scenarios/presets'),
  runSingleScenario: (payload: import('../types').ScenarioDefinition) =>
    request<import('../types').ScenarioRunResult>('/scenarios/run', { method: 'POST', body: JSON.stringify(payload) }),
  compareScenarios: (payload?: { scenarios?: import('../types').ScenarioDefinition[] }) =>
    request<import('../types').ScenarioComparisonResponse>('/scenarios/compare', { method: 'POST', body: JSON.stringify(payload ?? {}) }),
  activateScenario: (payload: { scenario_id: string; custom_params?: any }) =>
    request<import('../types').ScenarioActivationResponse>('/scenarios/activate', { method: 'POST', body: JSON.stringify(payload) }),
}

export { ApiError }

