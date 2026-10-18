from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import NetworkFailureSimulateRequest
from app.services.network_resilience_service import simulate_network_failure
from app.services.pipeline_state import state
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.gis.geo_loader import get_risk_zone_geometry
from app.config.settings import DEFAULT_COMM_RANGE_KM, DEFAULT_MAX_COMM_NODES, ENABLE_LEGACY_SHARED_STATE
from app.services.analysis_store import analysis_store

router = APIRouter()


@router.post("/network/resilience/simulate")
def simulate_resilience(req: NetworkFailureSimulateRequest):
    """
    Simulates failure of user-selected communication node(s), identifies
    isolated sensors and affected critical zones, and computes optimal recovery relay placement.
    """
    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{aid}' not found.")

    sensors = []
    comm_nodes = []

    if bundle and "optimization" in bundle:
        sensors = bundle["optimization"].get("selected_sensors", [])
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_optimization is not None:
        sensors = state.latest_optimization.get("selected_sensors", [])

    if bundle and "connectivity" in bundle:
        comm_nodes = bundle["connectivity"].get("comm_nodes", [])
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_connectivity is not None:
        comm_nodes = state.latest_connectivity.get("comm_nodes", [])

    study_area_ctx = bundle.get("study_area") if bundle else None

    if not sensors or not comm_nodes:
        if not ENABLE_LEGACY_SHARED_STATE and not bundle:
            raise HTTPException(
                status_code=400,
                detail="Missing analysis context. Run sensor optimization (POST /api/optimization/run) with analysis_id first."
            )
        # Generate initial sensor + connectivity setup if in legacy mode or bundle has risk map
        zones = (bundle["risk_map"].get("zones") if bundle and "risk_map" in bundle
                 else (state.latest_risk_map.get("zones") if ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map else get_risk_zone_geometry("default", study_area=study_area_ctx)))
        candidates = generate_candidates(study_area=study_area_ctx)
        engine = ClassicalOptimizationEngine()
        opt = engine.optimize(candidates, zones, 2.5, 8)
        sensors = opt.selected_sensors
        conn = analyze_connectivity(sensors, req.comm_range_km, DEFAULT_MAX_COMM_NODES)
        comm_nodes = conn.comm_nodes

    zones = (bundle["risk_map"].get("zones") if bundle and "risk_map" in bundle
             else (state.latest_risk_map.get("zones") if ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map else None))

    result = simulate_network_failure(
        selected_sensors=sensors,
        comm_nodes=comm_nodes,
        failed_node_ids=req.failed_node_ids,
        comm_range_km=req.comm_range_km,
        zones=zones
    )

    if aid:
        result["analysis_id"] = aid
        analysis_store.update_field(aid, "resilience", result)

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_resilience = result

    return result


@router.get("/network/resilience/latest")
def get_latest_resilience(analysis_id: Optional[str] = None):
    """Returns the latest resilience simulation and recovery plan."""
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "resilience" in bundle:
            return bundle["resilience"]
        req = NetworkFailureSimulateRequest(failed_node_ids=[], analysis_id=analysis_id)
        return simulate_resilience(req)

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_resilience is None:
        req = NetworkFailureSimulateRequest(failed_node_ids=[])
        return simulate_resilience(req)
    return state.latest_resilience
