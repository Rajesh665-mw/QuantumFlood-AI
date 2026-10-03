from fastapi import APIRouter, HTTPException
from app.schemas.schemas import SafeLocationEvaluateRequest
from app.services.safe_location_service import evaluate_safe_locations, load_candidate_safe_locations
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry

router = APIRouter()


@router.post("/safe-locations/evaluate")
def evaluate_locations(req: SafeLocationEvaluateRequest):
    """
    Evaluates candidate public facilities and assembly sites against the active
    risk map using transparent multi-criteria decision analysis (MCDA).
    """
    zones = None
    if state.latest_risk_map is not None:
        zones = state.latest_risk_map.get("zones")

    if not zones:
        # Fallback to default geometry if risk has not been run yet
        zones = get_risk_zone_geometry("default")

    results = evaluate_safe_locations(
        zones=zones,
        weight_elevation=req.weight_elevation,
        weight_risk=req.weight_risk,
        weight_distance=req.weight_distance,
        weight_accessibility=req.weight_accessibility,
        min_elevation_m=req.min_elevation_m,
        max_risk_level=req.max_risk_level
    )

    state.latest_safe_locations = results
    return results


@router.get("/safe-locations/candidates")
def get_candidate_facilities():
    """Returns the unrated catalog of candidate public facilities in the study area."""
    candidates = load_candidate_safe_locations()
    return {
        "candidates": candidates,
        "count": len(candidates),
        "data_provenance": "PARTIALLY_REAL"
    }


@router.get("/safe-locations/latest")
def get_latest_safe_locations():
    """Returns the latest evaluated safe locations from pipeline persistence."""
    if state.latest_safe_locations is None:
        # Evaluate on the fly with defaults
        zones = state.latest_risk_map.get("zones") if state.latest_risk_map else get_risk_zone_geometry("default")
        results = evaluate_safe_locations(zones)
        state.latest_safe_locations = results
        return results
    return state.latest_safe_locations
