from fastapi import APIRouter, HTTPException
from app.schemas.schemas import AdaptiveRedeployRequest
from app.services.adaptive_sensor_service import solve_adaptive_redeployment
from app.services.pipeline_state import state
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.gis.geo_loader import get_risk_zone_geometry

router = APIRouter()


@router.post("/sensors/redeploy")
def redeploy_sensors(req: AdaptiveRedeployRequest):
    """
    Computes optimal sensor transitions (KEEP, RELOCATE, ADD, REMOVE)
    given an updated flood risk map and sensor budget.
    """
    resolution = req.resolution or (state.latest_risk_map.get("resolution", "default") if state.latest_risk_map else "default")
    if state.latest_risk_map is None:
        from app.risk.risk_engine import generate_zone_risk_map
        state.latest_risk_map = generate_zone_risk_map(10.5, 500.0, 45.0, resolution=resolution)

    updated_zones = state.latest_risk_map["zones"]

    # Current baseline sensors
    current_sensors = []
    if req.use_active_sensors and state.latest_optimization is not None:
        current_sensors = state.latest_optimization.get("selected_sensors", [])

    if not current_sensors:
        # If no active optimization exists, create an initial baseline placement with neutral weights
        neutral_candidates = generate_candidates(resolution=resolution)
        engine = ClassicalOptimizationEngine()
        init_opt = engine.optimize(neutral_candidates, updated_zones, req.coverage_radius_km, req.sensor_budget)
        current_sensors = init_opt.selected_sensors

    redeploy_result = solve_adaptive_redeployment(
        current_sensors=current_sensors,
        updated_zones=updated_zones,
        sensor_budget=req.sensor_budget,
        coverage_radius_km=req.coverage_radius_km,
        resolution=resolution
    )

    state.latest_adaptive_redeployments = redeploy_result
    return redeploy_result


@router.get("/sensors/redeploy/latest")
def get_latest_redeployment():
    """Returns the latest adaptive sensor redeployment solution."""
    if state.latest_adaptive_redeployments is None:
        raise HTTPException(status_code=404, detail="No redeployment solution available. Run POST /api/sensors/redeploy.")
    return state.latest_adaptive_redeployments
