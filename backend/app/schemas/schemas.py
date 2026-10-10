from pydantic import BaseModel, Field
from typing import Optional


class ForecastTrainRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14, description="Days ahead to forecast")


class ForecastPredictRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)


class QmlForecastTrainRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14, description="Days ahead to forecast")
    n_layers: int = Field(default=2, ge=1, le=4, description="Variational layers (approved L=2)")
    max_iter: int = Field(default=40, ge=5, le=150, description="Optimizer maximum iterations")
    train_subsample: Optional[int] = Field(default=100, ge=20, le=500, description="Subsample of recent training records for interactive response")
    seed: int = Field(default=42, description="Deterministic random seed")


class QmlForecastPredictRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)


class ForecastCompareRequest(BaseModel):
    horizon_days: int = Field(default=1, ge=1, le=14)


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


class OptimizationRunRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=72, description="Sensor budget")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    comm_range_km: float = Field(default=4.0, gt=0, le=30)
    max_comm_nodes: int = Field(default=4, ge=1, le=30, description="Limited communication-node budget (UC-067)")


class QuantumOptimizationRunRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=30, description="Sensor budget K")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth p")
    shots: int = Field(default=1024, ge=100, le=10000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")
    formulation_mode: str = Field(default="pairwise", description="QUBO mode: pairwise or exact")
    max_candidates: int = Field(default=10, ge=2, le=16, description="Candidate subset limit for quantum simulation")


class OptimizationCompareRequest(BaseModel):
    num_sensors: int = Field(default=8, ge=1, le=30, description="Sensor budget K")
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    p: int = Field(default=1, ge=1, le=5, description="QAOA circuit depth p")
    shots: int = Field(default=1024, ge=100, le=10000, description="Measurement shots")
    seed: Optional[int] = Field(default=42, description="Random seed")
    max_candidates: int = Field(default=10, ge=2, le=16, description="Candidate subset limit for quantum simulation")


class NetworkAnalyzeRequest(BaseModel):
    comm_range_km: float = Field(default=4.0, gt=0, le=30)
    max_comm_nodes: int = Field(default=4, ge=1, le=30, description="Limited communication-node budget (UC-067)")


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


# --- Module 1: Safe Locations ---
class SafeLocationEvaluateRequest(BaseModel):
    weight_elevation: float = Field(default=0.25, ge=0.0, le=1.0)
    weight_risk: float = Field(default=0.35, ge=0.0, le=1.0)
    weight_distance: float = Field(default=0.20, ge=0.0, le=1.0)
    weight_accessibility: float = Field(default=0.20, ge=0.0, le=1.0)
    min_elevation_m: Optional[float] = Field(default=None, ge=0.0)
    max_risk_level: Optional[str] = Field(default=None, description="Filter: LOW, MODERATE, HIGH, CRITICAL")


# --- Module 2: Evacuation Routing ---
class EvacuationRouteRequest(BaseModel):
    origin_lat: float = Field(ge=-90.0, le=90.0)
    origin_lon: float = Field(ge=-180.0, le=180.0)
    dest_lat: float = Field(ge=-90.0, le=90.0)
    dest_lon: float = Field(ge=-180.0, le=180.0)
    origin_name: Optional[str] = Field(default="Origin Location")
    dest_name: Optional[str] = Field(default="Destination Facility")
    risk_penalty_beta: float = Field(default=3.0, ge=0.0, le=10.0)


# --- Module 3: Adaptive Sensor Redeployment ---
class AdaptiveRedeployRequest(BaseModel):
    sensor_budget: int = Field(default=8, ge=1, le=72)
    coverage_radius_km: float = Field(default=2.5, gt=0, le=20)
    resolution: str = Field(default="default")
    use_active_sensors: bool = Field(
        default=True,
        description="If true, use latest optimization deployment as baseline; otherwise optimize from scratch."
    )


# --- Module 4: Network Resilience ---
class NetworkFailureSimulateRequest(BaseModel):
    failed_node_ids: list[str] = Field(default_factory=list, description="List of comm node IDs to fail (e.g. ['CN-01'])")
    comm_range_km: float = Field(default=4.0, gt=0, le=30)


# --- Module 5: Emergency Resource Allocation ---
class ResourceAllocateRequest(BaseModel):
    rescue_teams: int = Field(default=5, ge=0, le=50)
    medical_teams: int = Field(default=3, ge=0, le=50)
    relief_units: int = Field(default=4, ge=0, le=50)
    emergency_vehicles: int = Field(default=4, ge=0, le=50)
    min_risk_level: str = Field(default="MODERATE", description="Minimum risk level for eligibility: MODERATE or HIGH")


# --- Module 6: Scenario Engine ---
class CustomScenarioInput(BaseModel):
    id: str = Field(default="custom")
    name: str = Field(default="Custom Scenario")
    water_level_m: float = Field(ge=0.0, le=30.0)
    inflow_ktcmd: float = Field(ge=0.0, le=5000.0)
    rainfall_mm_24h: float = Field(ge=0.0, le=500.0)
    resolution: str = Field(default="default")


class ScenarioCompareRequest(BaseModel):
    scenarios: Optional[list[CustomScenarioInput]] = Field(
        default=None, description="List of custom scenarios to compare; omit to compare default Baseline/Moderate/Severe suite."
    )


class ScenarioActivateRequest(BaseModel):
    scenario_id: str = Field(description="Preset scenario ID ('baseline', 'moderate', 'severe') or 'custom'")
    custom_params: Optional[CustomScenarioInput] = Field(default=None)

