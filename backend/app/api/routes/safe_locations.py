from typing import Optional
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import SafeLocationEvaluateRequest, ShelterRequestCreate, ShelterPortfolioQuantumRequest
from app.services.safe_location_service import evaluate_safe_locations, load_candidate_safe_locations
from app.services.pipeline_state import state
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.post("/safe-locations/evaluate")
def evaluate_locations(req: SafeLocationEvaluateRequest):
    """
    Evaluates candidate public facilities and assembly sites against the active
    risk map using transparent multi-criteria decision analysis (MCDA).
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

    zones = None
    if req.zones:
        zones = req.zones
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"].get("zones")
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        zones = state.latest_risk_map.get("zones")

    if not zones:
        # Fallback to geometry for this study area
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)

    results = evaluate_safe_locations(
        zones=zones,
        weight_elevation=req.weight_elevation,
        weight_risk=req.weight_risk,
        weight_distance=req.weight_distance,
        weight_accessibility=req.weight_accessibility,
        min_elevation_m=req.min_elevation_m,
        max_risk_level=req.max_risk_level,
        study_area=study_area_ctx,
    )

    if aid:
        results["analysis_id"] = aid
        analysis_store.update_field(aid, "safe_locations", results)

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_safe_locations = results

    return results


@router.get("/safe-locations/candidates")
def get_candidate_facilities(lat: float = None, lon: float = None, analysis_id: Optional[str] = None):
    """Returns candidate public facilities and operational shelters in the study area."""
    study_area_ctx = None
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if bundle and "study_area" in bundle:
            study_area_ctx = bundle["study_area"]

    if lat is not None and lon is not None:
        from app.services.study_area_service import resolve_study_area_context
        study_area_ctx = resolve_study_area_context(latitude=lat, longitude=lon, allow_fallback=ENABLE_LEGACY_SHARED_STATE)

    candidates = load_candidate_safe_locations(study_area=study_area_ctx)
    from app.services.safe_location_service import get_operational_shelters
    operational_shelters = get_operational_shelters(study_area=study_area_ctx)

    if study_area_ctx is not None:
        is_default = bool(study_area_ctx.get("is_default_location", False))
    else:
        from app.services.active_area import is_default_area
        is_default = is_default_area()
    return {
        "candidates": candidates,
        "operational_shelters": operational_shelters,
        "proposed_candidate_sites": candidates,
        "has_operational_shelters": len(operational_shelters) > 0,
        "count": len(candidates),
        "data_provenance": "PARTIALLY_REAL" if is_default else "MODELLED",
        "analysis_id": analysis_id,
    }


@router.get("/safe-locations/latest")
def get_latest_safe_locations(analysis_id: Optional[str] = None):
    """Returns the latest evaluated safe locations from pipeline persistence."""
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "safe_locations" in bundle:
            return bundle["safe_locations"]
        study_area_ctx = bundle.get("study_area")
        zones = bundle.get("risk_map", {}).get("zones") or get_risk_zone_geometry("default", study_area=study_area_ctx)
        results = evaluate_safe_locations(zones, study_area=study_area_ctx)
        results["analysis_id"] = analysis_id
        analysis_store.update_field(analysis_id, "safe_locations", results)
        return results

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_safe_locations is None:
        # Evaluate on the fly with defaults
        zones = state.latest_risk_map.get("zones") if state.latest_risk_map else get_risk_zone_geometry("default")
        results = evaluate_safe_locations(zones)
        state.latest_safe_locations = results
        return results
    return state.latest_safe_locations


@router.get("/safe-locations/requests")
def get_shelter_requests(shelter_id: Optional[str] = None):
    """Returns all submitted shelter resource requests, optionally filtered by shelter."""
    from app.services.shelter_request_service import list_shelter_requests
    return {
        "requests": list_shelter_requests(shelter_id=shelter_id),
        "count": len(list_shelter_requests(shelter_id=shelter_id))
    }


@router.post("/safe-locations/requests")
def submit_shelter_request(req: ShelterRequestCreate):
    """Creates a resource request from a shelter operator. Strictly rejects proposed candidate sites."""
    from app.services.safe_location_service import is_valid_operational_shelter
    from app.services.shelter_request_service import create_shelter_request

    # Enforce that requests can only be submitted for verified, operational shelters, never proposed candidate sites
    if not is_valid_operational_shelter(req.shelter_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot lodge resource request for facility '{req.shelter_name}' ({req.shelter_id}). "
                "Resource requests can only be submitted for verified, operational emergency shelters, "
                "not proposed candidate sites."
            )
        )

    try:
        new_req = create_shelter_request(
            shelter_id=req.shelter_id,
            shelter_name=req.shelter_name,
            resource_type=req.resource_type,
            requested_quantity=req.requested_quantity,
            urgency=req.urgency,
            notes=req.notes or ""
        )
        return {"status": "SUCCESS", "request": new_req}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/shelters/portfolio/quantum")
def optimize_shelter_portfolio(req: ShelterPortfolioQuantumRequest):
    """
    Evaluates a hybrid quantum QAOA portfolio selection of proposed shelter candidates.
    Maximizes MCDA suitability while enforcing spatial dispersion between selected sites.
    Verified operational shelters are completely unaffected.
    """
    from app.services.study_area_service import resolve_study_area_context
    from app.services.shelter_portfolio_optimizer import ShelterPortfolioOptimizer
    from app.gis.geo_loader import get_risk_zone_geometry
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    aid = req.analysis_id
    bundle = None
    if aid and analysis_store.is_valid_id(aid):
        bundle = analysis_store.get(aid)

    study_area_ctx = None
    if req.study_area:
        study_area_ctx = resolve_study_area_context(study_area_payload=req.study_area, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    elif bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]

    zones = None
    if bundle and "risk_map" in bundle:
        zones = bundle["risk_map"].get("zones")
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        zones = state.latest_risk_map.get("zones")

    if not zones:
        zones = get_risk_zone_geometry("default", study_area=study_area_ctx)

    eval_res = evaluate_safe_locations(zones=zones, study_area=study_area_ctx)
    candidate_sites = eval_res.get("proposed_candidate_sites", [])

    if not candidate_sites:
        raise HTTPException(status_code=400, detail="No proposed candidate shelter sites available in this study area.")

    optimizer = ShelterPortfolioOptimizer()
    try:
        report = optimizer.optimize_portfolio(
            candidate_shelters=candidate_sites,
            budget=req.budget,
            min_separation_km=req.min_separation_km,
            p=req.p,
            shots=req.shots,
            seed=req.seed,
        )
        report["study_area"] = study_area_ctx
        report["analysis_id"] = aid
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shelter portfolio optimization failed: {str(e)}")
