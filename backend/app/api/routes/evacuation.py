from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import EvacuationRouteRequest
from app.services.evacuation_service import calculate_evacuation_routes, load_road_network
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.post("/evacuation/route")
def plan_evacuation_route(req: EvacuationRouteRequest):
    """
    Computes model-based risk-penalized evacuation routing and alternative paths
    across the corridor road network.
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
    elif req.origin_lat is not None and req.origin_lon is not None:
        study_area_ctx = resolve_study_area_context(latitude=req.origin_lat, longitude=req.origin_lon, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    else:
        try:
            study_area_ctx = resolve_study_area_context(study_area_payload=None, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if req.zones:
        zones = req.zones
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"].get("zones")
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        zones = state.latest_risk_map.get("zones")
    else:
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)

    route_res = calculate_evacuation_routes(
        origin_lat=req.origin_lat,
        origin_lon=req.origin_lon,
        dest_lat=req.dest_lat,
        dest_lon=req.dest_lon,
        zones=zones,
        origin_name=req.origin_name or "Origin Location",
        dest_name=req.dest_name or "Destination Location",
        risk_penalty_beta=req.risk_penalty_beta,
        study_area=study_area_ctx,
    )

    if route_res.get("status") == "ERROR":
        raise HTTPException(status_code=500, detail=route_res.get("message"))

    if aid:
        route_res["analysis_id"] = aid
        analysis_store.update_field(aid, "evacuation", route_res)

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_evacuation_routes = route_res

    return route_res


@router.get("/evacuation/network")
def get_evacuation_road_network(lat: float = None, lon: float = None):
    """Returns the topological road network graph used for evacuation routing."""
    study_area_ctx = None
    if lat is not None and lon is not None:
        from app.services.study_area_service import resolve_study_area_context
        study_area_ctx = resolve_study_area_context(latitude=lat, longitude=lon, allow_fallback=ENABLE_LEGACY_SHARED_STATE)
    return load_road_network(study_area=study_area_ctx)


@router.get("/evacuation/latest")
def get_latest_evacuation_route(analysis_id: Optional[str] = None):
    """Returns the latest planned evacuation route."""
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "evacuation" not in bundle:
            raise HTTPException(status_code=404, detail=f"No evacuation route generated yet for analysis '{analysis_id}'. Run POST /api/evacuation/route.")
        return bundle["evacuation"]

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_evacuation_routes is None:
        raise HTTPException(status_code=404, detail="No evacuation route generated yet. Run POST /api/evacuation/route.")
    return state.latest_evacuation_routes
