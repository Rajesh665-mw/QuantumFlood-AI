export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'

export interface StudyArea {
  name: string
  region: string
  basin?: string
  scope_note?: string
  state: string
  bounding_box: { min_lat: number; max_lat: number; min_lon: number; max_lon: number }
  center: { lat: number; lon: number }
  river: string
  reference_gauge: string
  reference_gauge_coords?: { lat: number; lon: number }
  reference_gauge_source?: string
}

export interface AreaSelectResult {
  status: string
  is_default_location: boolean
  location_name: string
  display_name: string
  country?: string
  country_code?: string
  state?: string
  latitude?: number
  longitude?: number
  study_area: StudyArea
  data_availability: Record<string, any>
  map_config?: any
}

export interface LocationSearchResult {
  latitude: number
  longitude: number
  display_name: string
  country?: string
  city?: string
  bounding_box?: { min_lat: number; max_lat: number; min_lon: number; max_lon: number } | null
}

export interface DataProvenanceEntry {
  status: 'REAL_HISTORICAL' | 'SIMULATED_INPUT' | 'PARTIALLY_REAL' | 'PROJECT_DEFINED' | 'MODELLED_SPATIAL'
  reason: string
}

export interface DataProvenance {
  provenance: Record<string, DataProvenanceEntry>
  risk_zone_resolutions: Record<string, number>
}

export interface RealFloodEvent {
  event_id: string
  year: number
  month: string | null
  location: string
  peak_discharge_cusecs: number | null
  peak_discharge_cumecs: number | null
  severity_note: string
  citation: string
  data_source: string
}

export interface ExperimentSingleResult {
  engine_type: string
  objective_score: number
  coverage_percentage: number
  critical_zone_coverage_percentage: number
  sensors_selected: number
  comm_nodes_used: number
  connectivity_percentage: number
  uncovered_critical_zones: string[]
  execution_time_seconds: number
}

export interface ExperimentRecord {
  experiment_id: string
  timestamp: string
  config: { label: string; num_sensors: number; coverage_radius_km: number; comm_range_km: number; max_comm_nodes: number }
  num_candidates: number
  num_zones: number
  approach_a_greedy: ExperimentSingleResult
  approach_b_naive_topk: ExperimentSingleResult
  greedy_advantage_objective_score: number
}

export interface ExperimentRunRecord {
  run_timestamp: string
  resolution: string
  experiments: ExperimentRecord[]
  saved_to?: string
}

export interface MapConfig {
  min_zoom: number
  max_zoom: number
  default_zoom: number
  bounds_buffer_deg: number
  tile_url: string
  tile_subdomains: string[]
  tile_attribution: string
  no_wrap: boolean
  world_copy_jump: boolean
  max_bounds_viscosity: number
}

export interface MaxBounds {
  south_west: { lat: number; lon: number }
  north_east: { lat: number; lon: number }
}

export interface DatasetSummary {
  row_count: number
  columns: string[]
  date_range: { start: string; end: string }
  missing_values: Record<string, number>
  duplicate_rows: number
  numeric_summary: Record<string, { min: number; max: number; mean: number; std: number }>
  data_source_label: string
}

export interface HydroRecord {
  date: string
  rainfall_mm: number
  inflow_ktcmd: number
  water_level_m: number
  data_source: string
}

export interface ModelMetrics {
  mae: number
  rmse: number
  r2: number
}

export interface ForecastTrainResult {
  engine_type: string
  best_model_name: string
  metrics_by_model: Record<string, ModelMetrics>
  train_size: number
  test_size: number
  horizon_days: number
  feature_columns: string[]
}

export interface ForecastPrediction {
  based_on_date: string
  horizon_days: number
  predicted_water_level_m: number
  last_known_rainfall_mm: number
  last_known_inflow_ktcmd: number
  last_known_water_level_m: number
  model_used: string
}

export interface ForecastResults {
  engine_type: string
  best_model_name: string
  metrics_by_model: Record<string, ModelMetrics>
  predictions: { date: string; actual: number; predicted: number }[]
  horizon_days: number
  train_size: number
  test_size: number
  latest_prediction: ForecastPrediction | null
}

export interface QmlForecastResult {
  engine_type: string
  model_name: string
  horizon_days: number
  train_size: number
  test_size: number
  qubits: number
  n_qubits: number
  circuit_depth: number
  circuit_depth_layers: number
  trainable_parameters_count: number
  n_parameters: number
  optimal_parameters: number[]
  metrics: { mae: number; rmse: number; r2: number }
  test_mae: number
  test_rmse: number
  test_r2: number
  predictions: { date: string; actual: number; predicted: number }[]
  feature_names: string[]
  training_time_ms: number
  inference_time_ms: number
  training_time_s: number
  inference_time_s: number
  simulator_name: string
  affine_w: number
  affine_b: number
  metadata?: Record<string, any>
  latest_prediction?: ForecastPrediction | null
}

export interface QmlMultiseedRun {
  seed: number
  r2: number
  mae: number
  rmse: number
  runtime_s: number
}

export interface QmlMultiseedEvaluation {
  seeds_evaluated: number[]
  runs: QmlMultiseedRun[]
  summary: {
    mean_r2: number
    std_r2: number
    best_r2: number
    worst_r2: number
    mean_mae: number
    std_mae: number
    best_mae: number
    worst_mae: number
    mean_rmse: number
    std_rmse: number
  }
  academic_conclusion: string
}

export interface ForecastComparisonResponse {
  horizon_days: number
  classical: {
    model_name: string
    metrics: ModelMetrics
    predicted_water_level_m: number | null
    all_classical_models: Record<string, ModelMetrics>
    feature_columns: string[]
  }
  qml: {
    available: boolean
    error: string | null
    model_name: string
    metrics: ModelMetrics | null
    predicted_water_level_m: number | null
    training_time_s: number | null
    inference_time_s: number | null
    n_qubits: number
    circuit_depth: number
    n_parameters: number
    simulator: string
    features_used?: string[]
  }
  multiseed_evaluation?: QmlMultiseedEvaluation | null
  comparison?: {
    lower_rmse_model: string
    rmse_difference_m: number
    mae_difference_m: number
    observation: string
    scientific_note: string
  }
}

export interface RiskClassification {
  overall_risk: RiskLevel
  risk_score: number
  component_levels: Record<string, RiskLevel>
  driving_factor: string
  explanation: string
}

export interface RiskFactors {
  river_proximity_factor: number
  effective_water_level_m: number
  effective_inflow_ktcmd: number
  base_water_level_m: number
  base_inflow_ktcmd: number
  rainfall_mm_24h: number
  distance_to_river_km: number
  proximity_band: 'NEAR_RIVER' | 'MID_RANGE' | 'FAR_FROM_RIVER'
  attenuation_model: string
  decay_constant_km: number
  driving_factor: string
  explanation: string
}

export interface RiskZone {
  zone_id: string
  spatial_model?: string
  centroid: { lat: number; lon: number }
  bounds: { min_lat: number; max_lat: number; min_lon: number; max_lon: number }
  risk_level: RiskLevel
  risk_score: number
  distance_to_river_km: number
  risk_factors?: RiskFactors
}

export interface ProximityRule {
  near_river_km: number
  far_from_river_km: number
  description: string
}

export interface SpatialModel {
  type: string
  method: string
  decay_constant_km: number
  near_river_km: number
  far_from_river_km: number
  description: string
  note: string
}

export interface RiskMap {
  base_classification: RiskClassification
  zones: RiskZone[]
  critical_zone_count: number
  high_zone_count: number
  proximity_rule?: ProximityRule
  spatial_model?: SpatialModel
}

export interface MapLayers {
  study_area: StudyArea
  boundary: any
  river: any
  zones: RiskZone[]
  geometry_mode: string
  map_config: MapConfig
  max_bounds: MaxBounds
}

export interface Candidate {
  candidate_id: string
  lat: number
  lon: number
  zone_id: string
  risk_weight: number
  near_river: boolean
  placement_method?: string
}

export interface SelectedSensor {
  candidate_id: string
  lat: number
  lon: number
  zone_id: string
  risk_weight: number
  near_river: boolean
  placement_method?: string
  covered_zone_ids: string[]
}

export interface OptimizationResult {
  engine_type: string
  selected_sensors: SelectedSensor[]
  coverage_percentage: number
  weighted_risk_coverage: number
  total_weighted_risk: number
  critical_zone_coverage_percentage: number
  covered_zone_ids: string[]
  uncovered_priority_zone_ids: string[]
  num_candidates_considered: number
  num_sensors_requested: number
  num_sensors_selected: number
  coverage_per_sensor?: number
  minimal_sensors_for_max_coverage?: number
}

export interface CommNode {
  comm_node_id: string
  co_located_with: string
  lat: number
  lon: number
  connects_sensor_ids: string[]
}

export interface QuantumOptimizationResult {
  selected_candidate_ids: string[]
  selected_indices: number[]
  binary_solution: number[]
  objective_value: number
  weighted_coverage: number
  sensor_budget: number
  sensors_selected_count: number
  is_feasible: boolean
  qubo_energy: number
  qaoa_depth_p: number
  optimal_gamma: number[]
  optimal_beta: number[]
  shots: number
  backend_name: string
  execution_time_ms: number
  solution_probability: number
  total_qubits: number
  state_probabilities?: Record<string, number>
  candidate_coverage_details?: Array<{
    candidate_id: string
    candidate_index: number
    covered_zones_count: number
    individual_weight_sum: number
  }>
  metadata?: Record<string, any>
}

export interface QuantumOptimizationResponse {
  optimization: OptimizationResult
  quantum: QuantumOptimizationResult
  candidates_generated: number
  candidates_evaluated: number
  params: Record<string, any>
}

export interface MinimalNodesFrontierEntry {
  sensors_k: number
  max_coverage: number
  coverage_percentage: number
  marginal_gain: number
  coverage_per_sensor: number
  selected_sensors: string[]
  is_minimal_optimum: boolean
}

export interface MinimalNodesAnalysis {
  recommended_min_sensors: number
  max_achievable_coverage: number
  max_coverage_percentage: number
  total_risk_weight: number
  pareto_frontier: MinimalNodesFrontierEntry[]
  efficiency_analysis: string
}

export interface CommNodesTelemetry {
  sensor_nodes_count: number
  comm_nodes_used: number
  max_comm_nodes_allowed: number
  connectivity_percentage: number
  disconnected_nodes_count: number
  disconnected_sensor_ids: string[]
  relay_nodes_count: number
}

export interface CommunicationNodesAnalysis {
  comm_range_km: number
  max_comm_nodes_budget: number
  classical: CommNodesTelemetry
  quantum: CommNodesTelemetry
}

export interface OptimizationComparisonResponse {
  problem_size: {
    num_candidates: number
    num_zones: number
    budget_k: number
    coverage_radius_km: number
  }
  classical_result: {
    selected_sensor_ids: string[]
    num_sensors_selected: number
    weighted_coverage: number
    coverage_percentage: number
    critical_zone_coverage_pct: number
    coverage_per_sensor?: number
    minimal_sensors_for_max_coverage?: number
    execution_time_ms: number
  }
  quantum_result: {
    selected_sensor_ids: string[]
    num_sensors_selected: number
    weighted_coverage: number
    coverage_percentage: number
    critical_zone_coverage_pct: number
    coverage_per_sensor?: number
    minimal_sensors_for_max_coverage?: number
    is_feasible: boolean
    qaoa_depth_p: number
    shots: number
    solution_probability: number
    qubo_energy: number
    execution_time_ms: number
    optimal_gamma: number[]
    optimal_beta: number[]
  }
  exhaustive_ground_truth?: {
    optimal_weighted_coverage: number
    optimal_coverage_percentage: number
    optimal_subsets_count: number
    optimal_sensor_subsets: string[][]
    total_subsets_evaluated: number
  } | null
  comparison_metrics: {
    shared_sensors_count: number
    jaccard_similarity: number
    coverage_delta: number
    quantum_to_classical_ratio: number
    quantum_approximation_ratio?: number | null
    classical_approximation_ratio?: number | null
    quantum_matched_classical: boolean
    quantum_matched_global_optimum: boolean
  }
  communication_nodes_analysis?: CommunicationNodesAnalysis
  minimal_nodes_analysis?: MinimalNodesAnalysis
  academic_assessment: string
  total_candidates_pool?: number
}

export interface ConnectivityResult {
  comm_nodes: CommNode[]
  connected_sensor_ids: string[]
  disconnected_sensor_ids: string[]
  connections: { sensor_id: string; comm_node_id: string; distance_km: number }[]
  connectivity_percentage: number
  comm_range_km: number
  max_comm_nodes: number
  comm_nodes_used: number
  budget_exhausted: boolean
}

export interface CoverageSummary {
  total_zones: number
  total_coverage_percentage: number
  high_risk_zone_total: number
  high_risk_zone_covered: number
  critical_zone_total: number
  critical_zone_covered: number
  critical_zone_coverage_percentage: number
  sensor_budget: number
  sensors_deployed: number
  comm_node_budget: number
  comm_nodes_deployed: number
  comm_node_budget_exhausted: boolean
  connected_sensors: number
  disconnected_sensors: number
  connectivity_percentage: number
  uncovered_priority_zone_ids: string[]
}

export interface OptimizationRunResponse {
  optimization: OptimizationResult
  connectivity: ConnectivityResult
  coverage_summary: CoverageSummary
  candidates_generated: number
  params: { num_sensors: number; coverage_radius_km: number; comm_range_km: number; max_comm_nodes: number }
}

export interface Recommendation {
  priority: 'LOW' | 'MEDIUM' | 'HIGH'
  category: string
  zone_id?: string
  sensor_id?: string
  message: string
}

export interface Alert {
  level: RiskLevel
  message: string
}

export interface RecommendationsResponse {
  alerts: Alert[]
  recommendations: Recommendation[]
  priority_monitoring_areas: { zone_id: string; risk_level: RiskLevel; centroid: { lat: number; lon: number } }[]
}

export interface DashboardSummary {
  study_area: StudyArea
  forecast_available: boolean
  latest_forecast: ForecastPrediction | null
  risk_available: boolean
  base_risk: RiskClassification | null
  critical_zone_count: number | null
  high_zone_count: number | null
  optimization_available: boolean
  optimization: OptimizationResult | null
  connectivity_available: boolean
  connectivity: ConnectivityResult | null
  recommendations: RecommendationsResponse | null
}

// ==========================================
// MODULE 1: Safe Locations
// ==========================================
export interface SafeLocationScoreBreakdown {
  elevation_contribution: number
  low_risk_contribution: number
  distance_contribution: number
  accessibility_contribution: number
}

export interface SafeLocation {
  id: string
  name: string
  category: string
  lat: number
  lon: number
  elevation_m: number
  distance_to_river_km: number
  assigned_zone_id: string
  modelled_risk_level: RiskLevel
  risk_score: number
  primary_road_access: string
  road_class: string
  accessibility_score: number
  capacity_surveyed: boolean
  capacity_status: string
  raw_notes: string
  recommendation_score: number
  score_breakdown: SafeLocationScoreBreakdown
  explanation: string
  status_label: string
}

export interface SafeLocationEvaluationResponse {
  locations: SafeLocation[]
  total_candidates: number
  total_recommended: number
  weights_used: {
    elevation: number
    risk: number
    distance_to_risk: number
    accessibility: number
  }
  scientific_honesty_note: string
}

// ==========================================
// MODULE 2: Evacuation Routing
// ==========================================
export interface RouteSegment {
  edge_id: string
  road_name: string
  road_class: string
  distance_km: number
  modelled_risk_score: number
  risk_level: RiskLevel
  is_high_risk: boolean
  start_coord: { lat: number; lon: number }
  end_coord: { lat: number; lon: number }
  warning?: string | null
}

export interface EvacuationRoutePlan {
  label: string
  total_distance_km: number
  estimated_route_risk_score: number
  high_risk_segments_count: number
  coordinates: [number, number][]
  segments: RouteSegment[]
  summary_nodes: string[]
  start_node_name: string
  dest_node_name: string
}

export interface EvacuationRouteResponse {
  status: 'SUCCESS' | 'UNREACHABLE' | 'ERROR'
  origin: { lat: number; lon: number; name: string }
  destination: { lat: number; lon: number; name: string }
  primary_route: EvacuationRoutePlan | null
  alternative_route: EvacuationRoutePlan | null
  explanation: string
  data_provenance: Record<string, string>
  scientific_honesty_banner: string
}

// ==========================================
// MODULE 3: Adaptive Sensor Redeployment
// ==========================================
export interface RedeploymentAction {
  action: 'KEEP' | 'RELOCATE' | 'ADD' | 'REMOVE'
  sensor_id: string
  current_site: Candidate | null
  target_site: Candidate | null
  distance_km: number
  reason: string
}

export interface AdaptiveRedeploymentResponse {
  status: string
  actions: RedeploymentAction[]
  summary: {
    total_sensors_deployed: number
    sensors_kept: number
    sensors_relocated: number
    sensors_added: number
    sensors_removed: number
    baseline_coverage: {
      coverage_percentage: number
      critical_coverage_percentage: number
      weighted_risk_coverage: number
      total_weighted_risk: number
      covered_count: number
    }
    updated_coverage: {
      coverage_percentage: number
      critical_coverage_percentage: number
      weighted_risk_coverage: number
      total_weighted_risk: number
      covered_zones_count: number
    }
    improvements: {
      weighted_risk_coverage_gain: number
      coverage_percentage_gain: number
      critical_coverage_percentage_gain: number
    }
  }
  recommendation_narrative: string
  target_optimization: OptimizationResult
}

// ==========================================
// MODULE 4: Network Resilience
// ==========================================
export interface NetworkResilienceRecoveryNode {
  recovery_node_id: string
  candidate_id: string
  lat: number
  lon: number
  reconnected_sensor_ids: string[]
  reconnected_count: number
  restored_connections: {
    sensor_id: string
    recovery_node_id: string
    distance_km: number
    status: string
  }[]
}

export interface NetworkResilienceRecoveryPlan {
  action_type: 'DEPLOY_BACKUP_RELAY' | 'NO_VIABLE_RELAY_SITE'
  recommended_site: NetworkResilienceRecoveryNode | null
  sensors_reconnected: string[]
  reconnected_count: number
  post_recovery_connectivity_pct: number
  explanation: string
}

export interface NetworkResilienceResponse {
  status: string
  simulation_parameters: {
    total_comm_nodes: number
    failed_nodes_count: number
    failed_node_ids: string[]
    comm_range_km: number
  }
  metrics: {
    total_sensors: number
    baseline_connected: number
    baseline_connectivity_pct: number
    post_failure_connected: number
    post_failure_disconnected: number
    post_failure_connectivity_pct: number
    connectivity_loss_pct: number
    affected_critical_sensors: string[]
    surviving_nodes_count: number
  }
  network_state: {
    surviving_nodes: CommNode[]
    failed_nodes: CommNode[]
    active_connections: { sensor_id: string; comm_node_id: string; distance_km: number; status: string }[]
    severed_connections: { sensor_id: string; comm_node_id: string; distance_km: number; status: string }[]
    disconnected_sensors: SelectedSensor[]
  }
  recovery_plan: NetworkResilienceRecoveryPlan | null
}

// ==========================================
// MODULE 5: Emergency Resource Allocation
// ==========================================
export interface ZoneResourceAllocation {
  zone_id: string
  risk_level: RiskLevel
  risk_score: number
  distance_to_river_km: number
  centroid: { lat: number; lon: number }
  priority_score: number
  allocated_resources: Record<string, number>
  total_units_allocated: number
  explanation: string
}

export interface ResourceAllocationResponse {
  status: string
  parameters: {
    requested_budgets: Record<string, number>
    min_risk_level: string
  }
  summary: {
    eligible_zones_count: number
    zones_serviced_count: number
    allocated_quantities: Record<string, number>
    unallocated_quantities: Record<string, number>
    budget_exhaustion_pct: Record<string, number>
  }
  allocations: ZoneResourceAllocation[]
  mathematical_formulation: {
    objective: string
    decision_variables: string
    constraints: string[]
    quantum_readiness: string
  }
  scientific_honesty_note: string
}

// ==========================================
// MODULE 6: Multi-Scenario Comparison
// ==========================================
export interface ScenarioDefinition {
  id: string
  name: string
  description?: string
  water_level_m: number
  inflow_ktcmd: number
  rainfall_mm_24h: number
  severity?: string
  resolution?: string
}

export interface ScenarioRunMetrics {
  base_risk_level: RiskLevel
  critical_zones_count: number
  high_zones_count: number
  moderate_zones_count: number
  low_zones_count: number
  total_zones: number
  sensor_coverage_percentage: number
  critical_zone_coverage_percentage: number
  connected_sensors_count: number
  disconnected_sensors_count: number
  connectivity_percentage: number
  primary_evac_route_risk: number
  emergency_demand_index: number
  resources_serviced_zones: number
}

export interface ScenarioRunResult {
  scenario_id: string
  name: string
  inputs: {
    water_level_m: number
    inflow_ktcmd: number
    rainfall_mm_24h: number
    resolution: string
  }
  metrics: ScenarioRunMetrics
  pipeline_artifacts?: {
    risk_map: RiskMap
    optimization: OptimizationResult
    connectivity: ConnectivityResult
    coverage_summary: CoverageSummary
    recommendations: RecommendationsResponse
    safe_locations?: SafeLocationEvaluationResponse
    evacuation?: EvacuationRouteResponse
    resource_allocation?: ResourceAllocationResponse
  }
}

export interface ScenarioComparisonResponse {
  scenarios: ScenarioRunResult[]
  comparison_table: Record<string, any>[]
  total_scenarios: number
}

export interface ScenarioActivationResponse {
  status: string
  scenario_id: string
  name: string
  metrics: ScenarioRunMetrics
  message: string
}

