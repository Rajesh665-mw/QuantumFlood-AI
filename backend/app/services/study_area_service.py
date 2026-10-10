"""
Study Area Service
==================
Orchestrates the creation of a study area from a user-selected location:
  1. Geocodes the location (via location_service)
  2. Generates a bounding box / study area polygon
  3. Fetches available geographic features (via geospatial_service)
  4. Assesses data availability and provenance
  5. Configures the active area (via active_area)
  6. Generates simulated hydro data appropriate for the location

This is the main entry point for the "select location → analyze" workflow.
"""
import math
import logging
from typing import Optional, Dict, Any

from app.services.location_service import geocode, reverse_geocode
from app.services.geospatial_service import (
    get_primary_waterway,
    generate_synthetic_river,
    assess_data_availability,
)
from app.services.active_area import set_active_area, clear_active_area, get_active_area

logger = logging.getLogger(__name__)

# Default study area radius in degrees (approximately)
# 0.06 degrees ≈ 6.7 km at the equator
DEFAULT_HALF_SIZE_DEG = 0.06

# Maximum study area half-size to prevent enormous areas that would
# generate too many candidates for the QAOA statevector simulator
MAX_HALF_SIZE_DEG = 0.15  # ~16.7 km at equator

# Vijayawada detection — preserve existing behavior seamlessly
VIJAYAWADA_CENTER = {"lat": 16.50611, "lon": 80.60500}
VIJAYAWADA_DETECTION_RADIUS_DEG = 0.2


def _is_vijayawada_location(lat: float, lon: float) -> bool:
    """Check if the selected location is close to Vijayawada."""
    return (
        abs(lat - VIJAYAWADA_CENTER["lat"]) < VIJAYAWADA_DETECTION_RADIUS_DEG
        and abs(lon - VIJAYAWADA_CENTER["lon"]) < VIJAYAWADA_DETECTION_RADIUS_DEG
    )


def select_study_area(
    location_query: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    half_size_deg: Optional[float] = None,
    study_area_polygon: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Selects and configures a study area from either a text query or coordinates.

    Args:
        location_query: Text location (e.g. "Tokyo, Japan"). Geocoded if provided.
        latitude, longitude: Direct coordinates. Used if location_query is None.
        half_size_deg: Half-size of the study area bounding box in degrees.
        study_area_polygon: Optional custom polygon override (GeoJSON format).

    Returns:
        Complete study area configuration dict including:
        - location metadata
        - bounding box
        - river/water geometry
        - data availability
        - map configuration
    """
    # 1. Resolve location
    if location_query:
        geo_result = geocode(location_query)
        if geo_result is None:
            return {
                "status": "ERROR",
                "error": f"Location not found: '{location_query}'. Please try a different search term.",
                "query": location_query,
            }
        lat = geo_result["latitude"]
        lon = geo_result["longitude"]
        location_name = geo_result.get("city") or location_query
        display_name = geo_result["display_name"]
        country = geo_result.get("country", "")
        country_code = geo_result.get("country_code", "")
        state = geo_result.get("state", "")

        # Use Nominatim's bounding box only if caller did not provide an explicit half_size_deg
        nom_bbox = geo_result.get("bounding_box")
        if half_size_deg is None and nom_bbox:
            nom_span = max(
                nom_bbox["max_lat"] - nom_bbox["min_lat"],
                nom_bbox["max_lon"] - nom_bbox["min_lon"],
            )
            # Use Nominatim bbox if it's a reasonable size for a city/region
            if 0.02 < nom_span < 0.5:
                half_size_deg = nom_span / 2
        if half_size_deg is None:
            half_size_deg = DEFAULT_HALF_SIZE_DEG
    elif latitude is not None and longitude is not None:
        lat = latitude
        lon = longitude
        rev = reverse_geocode(lat, lon)
        if rev:
            city = (rev.get("city") or rev.get("town") or rev.get("village") or "").strip()
            state_val = (rev.get("state") or "").strip()
            country_val = (rev.get("country") or "").strip()
            location_name = city or state_val or country_val or f"{lat:.4f}, {lon:.4f}"
            display_name = rev.get("display_name") or location_name
            country = country_val
            country_code = rev.get("country_code", "")
            state = state_val
        else:
            location_name = f"{lat:.4f}, {lon:.4f}"
            display_name = location_name
            country = ""
            country_code = ""
            state = ""
    else:
        return {
            "status": "ERROR",
            "error": "Either 'location_query' or 'latitude'/'longitude' must be provided.",
        }

    # 2. Check if this is the default Vijayawada location
    if _is_vijayawada_location(lat, lon):
        # Revert to the default (Vijayawada) study area with real local data
        clear_active_area()
        from app.config.settings import STUDY_AREA, DATA_PROVENANCE
        return {
            "status": "OK",
            "is_default_location": True,
            "location_name": "Vijayawada",
            "display_name": "Vijayawada, Andhra Pradesh, India",
            "country": "India",
            "country_code": "in",
            "state": "Andhra Pradesh",
            "study_area": STUDY_AREA,
            "data_availability": DATA_PROVENANCE,
            "map_config": _build_map_config(STUDY_AREA["bounding_box"], STUDY_AREA["center"]),
        }

    # 3. Clamp half_size_deg
    if half_size_deg is None:
        half_size_deg = DEFAULT_HALF_SIZE_DEG
    half_size_deg = min(half_size_deg, MAX_HALF_SIZE_DEG)

    # 4. Generate bounding box
    if study_area_polygon:
        # Extract bounding box from provided polygon
        bbox = _bbox_from_polygon(study_area_polygon)
    else:
        bbox = {
            "min_lat": round(lat - half_size_deg, 6),
            "max_lat": round(lat + half_size_deg, 6),
            "min_lon": round(lon - half_size_deg, 6),
            "max_lon": round(lon + half_size_deg, 6),
        }

    center = {"lat": round(lat, 6), "lon": round(lon, 6)}

    # 5. Fetch water features from OSM
    river_feature = None
    river_source = "UNAVAILABLE"
    try:
        river_feature = get_primary_waterway(bbox)
        if river_feature:
            river_source = "REAL"
            logger.info("Found real waterway data for %s", location_name)
    except Exception as e:
        logger.warning("Failed to fetch waterways for %s: %s", location_name, e)

    # 6. Generate synthetic river if none found
    if river_feature is None:
        river_name = f"{location_name} (Synthetic Modeled River)"
        river_feature = generate_synthetic_river(bbox, name=river_name)
        river_source = "SIMULATED"
        logger.info("Generated synthetic river for %s", location_name)

    # 7. Assess data availability
    data_availability = assess_data_availability(bbox, has_waterways=(river_source == "REAL"))
    # Override river status with what we actually found
    data_availability["river_geometry"]["status"] = river_source

    # 8. Build study area config
    study_area_config = {
        "name": f"{location_name} Study Area",
        "region": f"{location_name} Region",
        "basin": f"{location_name} Basin",
        "scope_note": (
            f"Study area: a configurable region around {location_name}. "
            f"Geographic data sourced from OpenStreetMap where available. "
            f"Hydrological time series are simulated for this prototype."
        ),
        "state": state,
        "bounding_box": bbox,
        "center": center,
        "river": river_feature.get("properties", {}).get("name", "Study Waterway"),
        "reference_gauge": f"{location_name} Virtual Gauge",
        "reference_gauge_coords": center,
        "reference_gauge_source": "Generated study area center point (not a real gauge)",
        "river_geojson": river_feature,
    }

    # 9. Set as active area
    set_active_area(study_area_config)

    # 10. Build map config
    map_config = _build_map_config(bbox, center)

    return {
        "status": "OK",
        "is_default_location": False,
        "location_name": location_name,
        "display_name": display_name,
        "country": country,
        "country_code": country_code,
        "state": state,
        "latitude": lat,
        "longitude": lon,
        "study_area": study_area_config,
        "data_availability": data_availability,
        "map_config": map_config,
    }


def reset_to_default() -> Dict[str, Any]:
    """Resets the study area to the default Vijayawada corridor."""
    clear_active_area()
    from app.config.settings import STUDY_AREA, DATA_PROVENANCE
    return {
        "status": "OK",
        "message": "Reset to default Vijayawada–Krishna River Corridor study area.",
        "study_area": STUDY_AREA,
        "data_availability": DATA_PROVENANCE,
    }


def get_current_study_area() -> Dict[str, Any]:
    """Returns the currently active study area (dynamic or default)."""
    active = get_active_area()
    if active:
        return active
    from app.config.settings import STUDY_AREA
    return STUDY_AREA


def _build_map_config(bbox: dict, center: dict) -> dict:
    """Builds a Leaflet-compatible map configuration for the given area."""
    lat_span = bbox["max_lat"] - bbox["min_lat"]
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    max_span = max(lat_span, lon_span)

    # Estimate appropriate zoom level from span
    # Rough: zoom ≈ log2(360 / span) for Mercator
    if max_span > 0:
        default_zoom = max(8, min(15, int(math.log2(360 / max_span))))
    else:
        default_zoom = 12

    buffer = max(0.02, max_span * 0.3)

    return {
        "center": center,
        "default_zoom": default_zoom,
        "min_zoom": max(3, default_zoom - 4),
        "max_zoom": 17,
        "bounds_buffer_deg": round(buffer, 4),
        "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "tile_subdomains": ["a", "b", "c"],
        "tile_attribution": '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        "no_wrap": True,
        "world_copy_jump": False,
        "max_bounds_viscosity": 0.8,
        "max_bounds": {
            "south_west": {
                "lat": bbox["min_lat"] - buffer,
                "lon": bbox["min_lon"] - buffer,
            },
            "north_east": {
                "lat": bbox["max_lat"] + buffer,
                "lon": bbox["max_lon"] + buffer,
            },
        },
    }


def _bbox_from_polygon(polygon: dict) -> dict:
    """Extracts a bounding box from a GeoJSON Polygon."""
    coords = polygon.get("coordinates", [[]])[0]
    if not coords:
        return {"min_lat": 0, "max_lat": 0, "min_lon": 0, "max_lon": 0}
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    return {
        "min_lat": min(lats),
        "max_lat": max(lats),
        "min_lon": min(lons),
        "max_lon": max(lons),
    }
