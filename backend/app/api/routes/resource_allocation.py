from fastapi import APIRouter, HTTPException
from app.schemas.schemas import ResourceAllocateRequest
from app.services.resource_allocation_service import allocate_emergency_resources
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry

router = APIRouter()


@router.post("/resources/allocate")
def allocate_resources(req: ResourceAllocateRequest):
    """
    Optimally distributes user-specified quantities of emergency resources
    (Rescue Teams, Medical Units, Relief Supplies, Emergency Vehicles)
    across vulnerable zones.
    """
    zones = state.latest_risk_map.get("zones") if state.latest_risk_map else get_risk_zone_geometry("default")

    alloc_result = allocate_emergency_resources(
        zones=zones,
        rescue_teams=req.rescue_teams,
        medical_teams=req.medical_teams,
        relief_units=req.relief_units,
        emergency_vehicles=req.emergency_vehicles,
        min_risk_level=req.min_risk_level
    )

    state.latest_resource_allocations = alloc_result
    return alloc_result


@router.get("/resources/latest")
def get_latest_allocations():
    """Returns the latest emergency resource allocation state."""
    if state.latest_resource_allocations is None:
        # Default allocation run
        req = ResourceAllocateRequest()
        return allocate_resources(req)
    return state.latest_resource_allocations
