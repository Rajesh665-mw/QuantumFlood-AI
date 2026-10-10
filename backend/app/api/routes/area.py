"""
Area Selection API Routes
==========================
Endpoints for selecting, configuring, and resetting the active study area.
This is the primary entry point for the global location workflow.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.services.study_area_service import (
    select_study_area,
    reset_to_default,
    get_current_study_area,
)
from app.services.location_service import search_locations
from app.services.active_area import is_default_area, get_active_area
from app.services.pipeline_state import state

router = APIRouter()


class AreaSelectRequest(BaseModel):
    location_query: Optional[str] = Field(
        default=None,
        description="Text location to search (e.g. 'Tokyo, Japan', 'New Orleans, USA')"
    )
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    half_size_deg: float = Field(
        default=0.06, gt=0.005, le=0.15,
        description="Half-size of the study area in degrees (~0.06 ≈ 6.7km)"
    )
    study_area: Optional[dict] = Field(
        default=None,
        description="Optional custom study area polygon (GeoJSON Polygon geometry)"
    )


@router.post("/area/select")
def select_area(req: AreaSelectRequest):
    """
    Selects a new study area by geocoding a location or using coordinates.

    The system will:
    1. Geocode the location (if text query)
    2. Generate a study area bounding box
    3. Fetch available geographic data from OpenStreetMap
    4. Assess data availability and provenance
    5. Configure the active area for downstream analysis

    After selection, all analysis endpoints (risk, optimization, sensor
    placement) will operate on the newly selected area.
    """
    if not req.location_query and req.latitude is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'location_query' (text search) or 'latitude'/'longitude' (coordinates)."
        )

    if req.latitude is not None and req.longitude is None:
        raise HTTPException(status_code=400, detail="Both latitude and longitude must be provided.")
    if req.longitude is not None and req.latitude is None:
        raise HTTPException(status_code=400, detail="Both latitude and longitude must be provided.")

    result = select_study_area(
        location_query=req.location_query,
        latitude=req.latitude,
        longitude=req.longitude,
        half_size_deg=req.half_size_deg,
        study_area_polygon=req.study_area,
    )

    if result.get("status") == "ERROR":
        raise HTTPException(status_code=404, detail=result.get("error", "Location selection failed."))

    # Clear previous analysis results since the area has changed
    state.latest_risk_map = None
    state.latest_optimization = None
    state.latest_connectivity = None
    state.latest_recommendations = None
    state.latest_forecast = None
    state.latest_qml_forecast = None
    state.latest_safe_locations = None
    state.latest_evacuation_routes = None
    state.latest_adaptive_redeployments = None
    state.latest_resilience = None
    state.latest_resource_allocations = None
    state.active_scenario = None

    return result


@router.post("/area/reset")
def reset_area():
    """
    Resets the study area to the default Vijayawada–Krishna River Corridor.
    Clears all previous analysis results.
    """
    # Clear all analysis state
    state.latest_risk_map = None
    state.latest_optimization = None
    state.latest_connectivity = None
    state.latest_recommendations = None
    state.latest_forecast = None
    state.latest_qml_forecast = None
    state.latest_safe_locations = None
    state.latest_evacuation_routes = None
    state.latest_adaptive_redeployments = None
    state.latest_resilience = None
    state.latest_resource_allocations = None
    state.active_scenario = None

    return reset_to_default()


@router.get("/area/current")
def get_current_area():
    """Returns the currently active study area configuration."""
    area = get_current_study_area()
    active = get_active_area()

    # Build data availability info
    if is_default_area():
        from app.config.settings import DATA_PROVENANCE
        data_availability = DATA_PROVENANCE
    else:
        from app.services.geospatial_service import assess_data_availability
        bbox = area.get("bounding_box", {})
        data_availability = assess_data_availability(bbox) if bbox else {}

    return {
        "is_default_location": is_default_area(),
        "study_area": area,
        "data_availability": data_availability,
    }


@router.get("/area/search")
def search_area_locations(query: str, limit: int = 5):
    """Searches for places/cities matching query string."""
    if not query or len(query.strip()) < 2:
        return {"results": []}
    return {"results": search_locations(query, limit=limit)}
