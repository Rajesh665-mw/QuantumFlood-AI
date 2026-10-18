from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import AdaptiveRedeployRequest
from app.services.adaptive_sensor_service import solve_adaptive_redeployment
from app.services.pipeline_state import state
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.post("/sensors/redeploy")
def redeploy_sensors(req: AdaptiveRedeployRequest):
    """
    Computes optimal sensor transitions (KEEP, RELOCATE, ADD, REMOVE)
    given an updated flood risk map and sensor budget.
    """
    from app.services.study_area_service import resolve_study_area_context

    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle and not req.zones and not req.study_area:
            raise HTTPException(status_code=404, detail=f"Analysis session '{aid}' not found.")

    if req.study_area:
        study_area_ctx = resolve_study_area_context(study_area_payload=req.study_area, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    elif bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]
    else:
        try:
            study_area_ctx = resolve_study_area_context(study_area_payload=None, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    resolution = req.resolution or (
        bundle["risk_map"].get("resolution", "default") if bundle and "risk_map" in bundle
        else (state.latest_risk_map.get("resolution", "default") if ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map else "default")
    )

    if req.zones:
        updated_zones = req.zones
    elif bundle and "risk_map" in bundle:
        updated_zones = bundle["risk_map"]["zones"]
    elif req.study_area:
        updated_zones = get_risk_zone_geometry(resolution, study_area=study_area_ctx)
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        updated_zones = state.latest_risk_map["zones"]
    elif not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(
            status_code=400,
            detail="Missing required context: provide 'analysis_id' with an existing risk map, or explicit 'study_area' / 'zones'."
        )
    else:
        from app.risk.risk_engine import generate_zone_risk_map
        gen_map = generate_zone_risk_map(10.5, 500.0, 45.0, resolution=resolution, study_area=study_area_ctx)
        updated_zones = gen_map["zones"]

    # Current baseline sensors
    current_sensors = []
    if req.use_active_sensors:
        if bundle and "optimization" in bundle:
            current_sensors = bundle["optimization"].get("selected_sensors", [])
        elif ENABLE_LEGACY_SHARED_STATE and state.latest_optimization is not None:
            current_sensors = state.latest_optimization.get("selected_sensors", [])

    if not current_sensors:
        # If no active optimization exists, create an initial baseline placement with neutral weights
        neutral_candidates = generate_candidates(resolution=resolution, study_area=study_area_ctx)
        engine = ClassicalOptimizationEngine()
        init_opt = engine.optimize(neutral_candidates, updated_zones, req.coverage_radius_km, req.sensor_budget)
        current_sensors = init_opt.selected_sensors

    redeploy_result = solve_adaptive_redeployment(
        current_sensors=current_sensors,
        updated_zones=updated_zones,
        sensor_budget=req.sensor_budget,
        coverage_radius_km=req.coverage_radius_km,
        resolution=resolution,
        study_area=study_area_ctx,
    )

    if aid:
        redeploy_result["analysis_id"] = aid
        analysis_store.update_field(aid, "adaptive_redeployment", redeploy_result)

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_adaptive_redeployments = redeploy_result

    return redeploy_result


@router.get("/sensors/redeploy/latest")
def get_latest_redeployment(analysis_id: Optional[str] = None):
    """Returns the latest adaptive sensor redeployment solution."""
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "adaptive_redeployment" not in bundle:
            raise HTTPException(status_code=404, detail=f"No redeployment solution available for analysis '{analysis_id}'.")
        return bundle["adaptive_redeployment"]

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_adaptive_redeployments is None:
        raise HTTPException(status_code=404, detail="No redeployment solution available. Run POST /api/sensors/redeploy.")
    return state.latest_adaptive_redeployments
