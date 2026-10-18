from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import (
    ResourceAllocateRequest,
    ShelterAllocationRequest,
    ShelterFulfillmentRequest,
    ResourceQuantumOptimizeRequest,
    ResourceQuantumApplyRequest,
)
from app.services.resource_allocation_service import allocate_emergency_resources
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.post("/resources/allocate")
def allocate_resources(req: ResourceAllocateRequest):
    """
    Optimally distributes user-specified quantities of emergency resources
    (Rescue Teams, Medical Units, Relief Supplies, Emergency Vehicles)
    across vulnerable zones.
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

    if req.zones:
        zones = req.zones
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"].get("zones")
    elif req.study_area:
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        zones = state.latest_risk_map.get("zones")
    elif not aid:
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)
    elif not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(
            status_code=400,
            detail="Missing required context: provide 'analysis_id' with an existing risk map, or explicit 'study_area' / 'zones'."
        )
    else:
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)

    # Ensure zones have baseline risk_score and risk_level if not present
    for z in (zones or []):
        if "risk_score" not in z or "risk_level" not in z:
            dist = z.get("distance_to_river_km", 2.0)
            if dist < 0.8:
                z["risk_score"] = 4
                z["risk_level"] = "CRITICAL"
            elif dist < 1.8:
                z["risk_score"] = 3
                z["risk_level"] = "HIGH"
            elif dist < 3.0:
                z["risk_score"] = 2
                z["risk_level"] = "MODERATE"
            else:
                z["risk_score"] = 1
                z["risk_level"] = "LOW"

    alloc_result = allocate_emergency_resources(
        zones=zones,
        rescue_teams=req.rescue_teams,
        medical_teams=req.medical_teams,
        relief_units=req.relief_units,
        emergency_vehicles=req.emergency_vehicles,
        min_risk_level=req.min_risk_level
    )

    if aid:
        alloc_result["analysis_id"] = aid
        analysis_store.update_field(aid, "resources", alloc_result)

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_resource_allocations = alloc_result

    return alloc_result


@router.get("/resources/latest")
def get_latest_allocations(analysis_id: Optional[str] = None):
    """Returns the latest emergency resource allocation state."""
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "resources" in bundle:
            return bundle["resources"]
        req = ResourceAllocateRequest(analysis_id=analysis_id)
        return allocate_resources(req)

    if state.latest_resource_allocations is None:
        req = ResourceAllocateRequest()
        return allocate_resources(req)
    return state.latest_resource_allocations


# --- Section 5: Resource Planning, Inventory & Fulfillment ---

@router.get("/resources/inventory")
def get_inventory():
    """Returns current central warehouse inventory stock levels."""
    from app.services.shelter_request_service import get_inventory_status
    return {"inventory": get_inventory_status()}


@router.get("/resources/demand-summary")
def get_demand_summary():
    """Computes aggregated resource demand, fulfillment ratios, and shortage metrics."""
    from app.services.shelter_request_service import calculate_demand_summary
    return calculate_demand_summary()


@router.get("/resources/audit-log")
def get_audit_log():
    """Returns chronological audit trail of allocation and fulfillment actions."""
    from app.services.shelter_request_service import get_audit_trail
    return {"audit_trail": get_audit_trail()}


@router.post("/resources/allocate-request")
def allocate_to_shelter(req: "ShelterAllocationRequest"):
    """Allocates inventory to an existing shelter request without exceeding stock."""
    from app.services.shelter_request_service import allocate_shelter_request
    try:
        return allocate_shelter_request(req.request_id, req.allocated_quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resources/fulfill-request")
def fulfill_shelter(req: "ShelterFulfillmentRequest"):
    """Marks allocated supplies as fulfilled/delivered to shelter."""
    from app.services.shelter_request_service import fulfill_shelter_request
    try:
        return fulfill_shelter_request(req.request_id, req.fulfilled_quantity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resources/shelter-requests/quantum-optimize")
def quantum_optimize_shelter_resources(req: ResourceQuantumOptimizeRequest):
    """
    Executes hybrid quantum QAOA resource knapsack optimization for pending shelter requests.
    Balances urgency with fairness while guaranteeing strictly zero inventory over-allocation.
    """
    from app.services.quantum_resource_allocator import QuantumResourceAllocator
    allocator = QuantumResourceAllocator()
    try:
        return allocator.optimize_allocation(
            resource_type=req.resource_type,
            p=req.p,
            shots=req.shots,
            seed=req.seed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quantum resource allocation failed: {str(e)}")


@router.post("/resources/shelter-requests/quantum-apply")
def quantum_apply_shelter_resources(req: ResourceQuantumApplyRequest):
    """
    Applies approved allocations to live shelter inventory via verified classical guards.
    """
    from app.services.quantum_resource_allocator import QuantumResourceAllocator
    allocator = QuantumResourceAllocator()
    try:
        plan = [{"request_id": a.request_id, "allocated_quantity": a.allocated_quantity} for a in req.allocations]
        return allocator.apply_plan(plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Applying quantum resource allocations failed: {str(e)}")
