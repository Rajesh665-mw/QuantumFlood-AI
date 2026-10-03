from fastapi import APIRouter, HTTPException
from app.schemas.schemas import EvacuationRouteRequest
from app.services.evacuation_service import calculate_evacuation_routes, load_road_network
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry

router = APIRouter()


@router.post("/evacuation/route")
def plan_evacuation_route(req: EvacuationRouteRequest):
    """
    Computes model-based risk-penalized evacuation routing and alternative paths
    across the corridor road network.
    """
    zones = state.latest_risk_map.get("zones") if state.latest_risk_map else get_risk_zone_geometry("default")

    route_res = calculate_evacuation_routes(
        origin_lat=req.origin_lat,
        origin_lon=req.origin_lon,
        dest_lat=req.dest_lat,
        dest_lon=req.dest_lon,
        zones=zones,
        origin_name=req.origin_name or "Origin Location",
        dest_name=req.dest_name or "Destination Location",
        risk_penalty_beta=req.risk_penalty_beta
    )

    if route_res.get("status") == "ERROR":
        raise HTTPException(status_code=500, detail=route_res.get("message"))

    state.latest_evacuation_routes = route_res
    return route_res


@router.get("/evacuation/network")
def get_evacuation_road_network():
    """Returns the topological road network graph used for evacuation routing."""
    return load_road_network()


@router.get("/evacuation/latest")
def get_latest_evacuation_route():
    """Returns the latest planned evacuation route."""
    if state.latest_evacuation_routes is None:
        raise HTTPException(status_code=404, detail="No evacuation route generated yet. Run POST /api/evacuation/route.")
    return state.latest_evacuation_routes
