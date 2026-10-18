from pydantic import BaseModel, Field, validator
from typing import Optional, Any


class BoundingBoxPayload(BaseModel):
    min_lat: float = Field(ge=-90.0, le=90.0)
    max_lat: float = Field(ge=-90.0, le=90.0)
    min_lon: float = Field(ge=-180.0, le=180.0)
    max_lon: float = Field(ge=-180.0, le=180.0)

    @validator("max_lat")
    def validate_lat_order(cls, v, values):
        if "min_lat" in values and v < values["min_lat"]:
            raise ValueError("max_lat must be greater than or equal to min_lat")
        return v

    @validator("max_lon")
    def validate_lon_order(cls, v, values):
        if "min_lon" in values and v < values["min_lon"]:
            raise ValueError("max_lon must be greater than or equal to min_lon")
        return v


class CenterCoordsPayload(BaseModel):
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)


class StudyAreaPayload(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    region: Optional[str] = Field(default=None, max_length=200)
    basin: Optional[str] = Field(default=None, max_length=200)
    scope_note: Optional[str] = Field(default=None, max_length=500)
    state: Optional[str] = Field(default=None, max_length=200)
    bounding_box: Optional[BoundingBoxPayload] = None
    center: Optional[CenterCoordsPayload] = None
    river: Optional[str] = Field(default=None, max_length=200)
    reference_gauge: Optional[str] = Field(default=None, max_length=200)
    reference_gauge_coords: Optional[CenterCoordsPayload] = None
    reference_gauge_source: Optional[str] = Field(default=None, max_length=200)
    river_geojson: Optional[dict] = None
    is_default_location: Optional[bool] = None
    use_benchmark: Optional[bool] = Field(default=None, description="Explicitly request the default Vijayawada benchmark corridor")


class ForecastTrainRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14, description="Days ahead to forecast")


class ForecastPredictRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class QmlForecastTrainRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14, description="Days ahead to forecast")
    n_layers: int = Field(default=2, ge=1, le=4, description="Variational layers (approved L=2)")
    max_iter: int = Field(default=40, ge=5, le=150, description="Optimizer maximum iterations")
    train_subsample: Optional[int] = Field(default=100, ge=20, le=500, description="Subsample of recent training records for interactive response")
    seed: int = Field(default=42, description="Deterministic random seed")


class QmlForecastPredictRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class ForecastCompareRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class RiskGenerateRequest(BaseModel):
    water_level_m: Optional[float] = Field(default=None, ge=0)
    inflow_ktcmd: Optional[float] = Field(default=None, ge=0)
    rainfall_mm_24h: Optional[float] = Field(default=None, ge=0)
    use_latest_forecast: bool = Field(
        default=True,
        description="If true and explicit values are not provided, use the latest trained forecast."
    )
    forecast_model_preference: Optional[str] = Field(
        default="classical",
        description="Forecast source to draw from when use_latest_forecast is True: 'classical' or 'qml'."
    )
    resolution: str = Field(default="default", description="Risk-zone grid resolution: low/default/high")
    study_area: Optional[StudyAreaPayload] = Field(
        default=None,
        description="Request-scoped study area context. Eliminates dependency on mutable active area singleton."
    )
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")
    use_benchmark: Optional[bool] = Field(
        default=None,
        description="Explicitly request the default Vijayawada benchmark corridor"
    )


class OptimizationRunRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=72, description="Sensor budget")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    comm_range_km: float = Field(default=4.0, gt=0, le=30)
    max_comm_nodes: int = Field(default=4, ge=1, le=30, description="Limited communication-node budget (UC-067)")
    study_area: Optional[StudyAreaPayload] = Field(
        default=None,
        description="Request-scoped study area context for sensor candidate placement."
    )
    zones: Optional[list[dict]] = Field(
        default=None,
        description="Optional explicit zone risk list. When provided, optimizes against these zones."
    )
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class QuantumOptimizationRunRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=30, description="Sensor budget K")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth p")
    shots: int = Field(default=1024, ge=100, le=10000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")
    formulation_mode: str = Field(default="pairwise", description="QUBO mode: pairwise or exact")
    max_candidates: int = Field(default=10, ge=2, le=16, description="Candidate subset limit for quantum simulation")
    min_distance_km: Optional[float] = Field(default=None, ge=0.0, le=20.0, description="Optional minimum spatial separation")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class OptimizationCompareRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=30, description="Sensor budget K")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth p")
    shots: int = Field(default=1024, ge=100, le=10000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")
    max_candidates: int = Field(default=10, ge=2, le=16, description="Candidate subset limit for quantum simulation")
    min_distance_km: Optional[float] = Field(default=None, ge=0.0, le=20.0, description="Optional minimum spatial separation")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class NetworkAnalyzeRequest(BaseModel):
    comm_range_km: float = Field(default=4.0, gt=0, le=30)
    max_comm_nodes: int = Field(default=4, ge=1, le=30, description="Limited communication-node budget (UC-067)")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class ExperimentConfigItem(BaseModel):
    label: str = Field(description="Human-readable label, e.g. 'small'/'medium'/'large'")
    num_sensors: int = Field(ge=1, le=72)
    coverage_radius_km: float = Field(gt=0, le=20)
    comm_range_km: float = Field(gt=0, le=30)
    max_comm_nodes: int = Field(ge=1, le=30)


class ExperimentRunRequest(BaseModel):
    configs: Optional[list[ExperimentConfigItem]] = Field(
        default=None, description="Custom experiment configs; omit to use the default small/medium/large suite."
    )
    resolution: str = Field(default="default", description="Risk-zone grid resolution: low/default/high")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 1: Safe Locations ---
class SafeLocationEvaluateRequest(BaseModel):
    weight_elevation: float = Field(default=0.25, ge=0.0, le=1.0)
    weight_risk: float = Field(default=0.35, ge=0.0, le=1.0)
    weight_distance: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_accessibility: float = Field(default=0.20, ge=0.0, le=1.0)
    min_elevation_m: Optional[float] = Field(default=None, ge=0.0)
    max_risk_level: Optional[str] = Field(default=None, description="Filter: LOW, MODERATE, HIGH, CRITICAL")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 2: Evacuation Routing ---
class EvacuationRouteRequest(BaseModel):
    origin_lat: float = Field(ge=-90.0, le=90.0)
    origin_lon: float = Field(ge=-180.0, le=180.0)
    dest_lat: float = Field(ge=-90.0, le=90.0)
    dest_lon: float = Field(ge=-180.0, le=180.0)
    origin_name: Optional[str] = Field(default="Origin Location")
    dest_name: Optional[str] = Field(default="Destination Facility")
    risk_penalty_beta: float = Field(default=3.0, ge=0.0, le=10.0)
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 3: Adaptive Sensor Redeployment ---
class AdaptiveRedeployRequest(BaseModel):
    sensor_budget: int = Field(default=8, ge=1, le=72)
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    resolution: str = Field(default="default")
    use_active_sensors: bool = Field(
        default=True,
        description="If true, use latest optimization deployment as baseline; otherwise optimize from scratch."
    )
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 4: Network Resilience ---
class NetworkFailureSimulateRequest(BaseModel):
    failed_node_ids: list[str] = Field(default_factory=list, description="List of comm node IDs to fail (e.g. ['CN-01'])")
    comm_range_km: float = Field(default=4.0, gt=0, le=30)
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 5: Emergency Resource Allocation ---
class ResourceAllocateRequest(BaseModel):
    rescue_teams: int = Field(default=5, ge=0, le=50)
    medical_teams: int = Field(default=3, ge=0, le=50)
    relief_units: int = Field(default=4, ge=0, le=50)
    emergency_vehicles: int = Field(default=4, ge=0, le=50)
    min_risk_level: str = Field(default="MODERATE", description="Minimum risk level for eligibility: MODERATE or HIGH")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    zones: Optional[list[dict]] = Field(default=None, description="Optional explicit zone risk list")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


# --- Module 6: Scenario Engine ---
class CustomScenarioInput(BaseModel):
    id: str = Field(default="custom")
    name: str = Field(default="Custom Scenario")
    water_level_m: float = Field(ge=0.0, le=30.0)
    inflow_ktcmd: float = Field(ge=0.0, le=5000.0)
    rainfall_mm_24h: float = Field(ge=0.0, le=500.0)
    resolution: str = Field(default="default")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class ScenarioCompareRequest(BaseModel):
    scenarios: Optional[list[CustomScenarioInput]] = Field(
        default=None, description="List of custom scenarios to compare; omit to compare default Baseline/Moderate/Severe suite."
    )


class ScenarioActivateRequest(BaseModel):
    scenario_id: str = Field(description="Preset scenario ID ('baseline', 'moderate', 'severe') or 'custom'")
    custom_params: Optional[CustomScenarioInput] = Field(default=None)


# --- Section 4 & 5: Shelter Requests & Resource Fulfillment ---
class ShelterRequestCreate(BaseModel):
    shelter_id: str = Field(description="Shelter identifier")
    shelter_name: str = Field(description="Name of the shelter facility")
    resource_type: str = Field(description="Type of resource requested (e.g. Clean Drinking Water (L))")
    requested_quantity: int = Field(gt=0, description="Quantity requested")
    urgency: str = Field(default="MODERATE", description="Urgency: LOW, MODERATE, HIGH, CRITICAL")
    notes: Optional[str] = Field(default="", description="Operator operational notes")


class ShelterAllocationRequest(BaseModel):
    request_id: str = Field(description="ID of the shelter request to allocate for")
    allocated_quantity: int = Field(ge=0, description="Units to allocate from inventory")


class ShelterFulfillmentRequest(BaseModel):
    request_id: str = Field(description="ID of the shelter request to fulfill")
    fulfilled_quantity: int = Field(ge=0, description="Units delivered / fulfilled")


class ShelterPortfolioQuantumRequest(BaseModel):
    budget: int = Field(default=3, ge=1, le=8, description="Number of proposed candidate sites to activate in portfolio")
    min_separation_km: float = Field(default=2.0, ge=0.5, le=10.0, description="Minimum spatial separation in km")
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth")
    shots: int = Field(default=512, ge=100, le=5000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")
    study_area: Optional[StudyAreaPayload] = Field(default=None, description="Request-scoped study area context")
    analysis_id: Optional[str] = Field(default=None, description="Request-scoped analysis identifier")


class ResourceQuantumOptimizeRequest(BaseModel):
    resource_type: str = Field(description="Resource type name to optimize allocations for")
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth")
    shots: int = Field(default=512, ge=100, le=5000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")


class ResourceQuantumApplyItem(BaseModel):
    request_id: str
    allocated_quantity: int


class ResourceQuantumApplyRequest(BaseModel):
    allocations: list[ResourceQuantumApplyItem]

