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
    set_as_active: bool = True,
) -> Dict[str, Any]:
    """
    Selects and configures a study area from either a text query or coordinates.

    Args:
        location_query: Text location (e.g. "Tokyo, Japan"). Geocoded if provided.
        latitude, longitude: Direct coordinates. Used if location_query is None.
        half_size_deg: Half-size of the study area bounding box in degrees.
        study_area_polygon: Optional custom polygon override (GeoJSON format).
        set_as_active: If True, sets active area singleton (legacy mode). If False, purely returns context.

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
        location_name = (
            geo_result.get("name_en")
            or geo_result.get("name")
            or geo_result.get("city")
            or location_query
        )
        if any(ord(c) > 127 for c in str(location_name)):
            clean_q = location_query.split(",")[0].strip()
            if clean_q and all(ord(c) <= 127 for c in clean_q):
                location_name = clean_q
        display_name = geo_result.get("display_name", location_query)
        if any(ord(c) > 127 for c in str(display_name)):
            country_val = geo_result.get("country", "")
            display_name = f"{location_name}, {country_val}" if country_val else str(location_name)
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
            city = (
                rev.get("name_en")
                or rev.get("name")
                or rev.get("city")
                or rev.get("town")
                or rev.get("village")
                or ""
            ).strip()
            state_val = (rev.get("state") or "").strip()
            country_val = (rev.get("country") or "").strip()
            location_name = city or state_val or country_val or f"{lat:.4f}, {lon:.4f}"
            if any(ord(c) > 127 for c in str(location_name)):
                location_name = rev.get("name_en") or f"{lat:.4f}, {lon:.4f}"
            display_name = rev.get("display_name") or location_name
            if any(ord(c) > 127 for c in str(display_name)):
                display_name = f"{location_name}, {country_val}" if country_val else str(location_name)
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
        if set_as_active:
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
            r_props = river_feature.get("properties", {})
            r_name = r_props.get("name", "")
            if any(ord(c) > 127 for c in str(r_name)):
                r_props["name"] = f"{location_name} River"
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

    # 9. Set as active area only when requested
    if set_as_active:
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


def resolve_study_area_context(
    study_area_payload: Optional[Any] = None,
    location_query: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    half_size_deg: Optional[float] = None,
    study_area_polygon: Optional[Dict[str, Any]] = None,
    use_benchmark: bool = False,
    allow_fallback: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Produces a validated, request-scoped study area context dictionary without mutating
    any module-level or process-wide active area singleton.

    Priority order:
    1. Explicit benchmark flag (use_benchmark=True) -> returns documented Vijayawada benchmark
    2. Direct study_area_payload dictionary (validated & sanitized)
    3. Explicit coordinates (latitude, longitude) or location_query (geocoded/resolved)
    4. If allow_fallback is True (or ENABLE_LEGACY_SHARED_STATE is True):
       - Global active area (if set)
       - Default Vijayawada study area (STUDY_AREA from settings)
    5. If allow_fallback is False:
       - Raises ValueError demanding explicit study area or benchmark flag.
    """
    from app.config.settings import STUDY_AREA, ENABLE_LEGACY_SHARED_STATE

    if allow_fallback is None:
        allow_fallback = ENABLE_LEGACY_SHARED_STATE

    # Case 0: Explicit benchmark mode requested
    if use_benchmark:
        sa = dict(STUDY_AREA)
        sa["is_default_location"] = True
        return sa

    # Case 1: Direct study_area_payload provided
    if study_area_payload:
        if hasattr(study_area_payload, "model_dump"):
            payload = study_area_payload.model_dump(exclude_none=True)
        elif hasattr(study_area_payload, "dict"):
            payload = study_area_payload.dict(exclude_none=True)
        elif isinstance(study_area_payload, dict):
            payload = dict(study_area_payload)
        else:
            payload = {}

        if payload.get("use_benchmark") is True:
            sa = dict(STUDY_AREA)
            sa["is_default_location"] = True
            return sa

        if "study_area" in payload and isinstance(payload["study_area"], dict):
            payload = payload["study_area"]

        bbox = payload.get("bounding_box")
        if bbox and isinstance(bbox, dict):
            min_lat = float(bbox.get("min_lat", 0))
            max_lat = float(bbox.get("max_lat", 0))
            min_lon = float(bbox.get("min_lon", 0))
            max_lon = float(bbox.get("max_lon", 0))

            if not (-90.0 <= min_lat <= max_lat <= 90.0 and -180.0 <= min_lon <= max_lon <= 180.0):
                raise ValueError(f"Invalid bounding box coordinates: {bbox}")

            center = payload.get("center")
            if not center or not isinstance(center, dict):
                center = {
                    "lat": round((min_lat + max_lat) / 2.0, 6),
                    "lon": round((min_lon + max_lon) / 2.0, 6),
                }

            name = str(payload.get("name") or "Custom Study Area").strip()[:100]
            region = str(payload.get("region") or f"{name} Region").strip()[:100]
            state_name = str(payload.get("state") or "").strip()[:100]
            river_name = str(payload.get("river") or "Study Waterway").strip()[:100]

            river_geojson = payload.get("river_geojson")
            if not river_geojson or not isinstance(river_geojson, dict):
                if _is_vijayawada_location(center["lat"], center["lon"]):
                    from app.gis.geo_loader import _load_river_geojson
                    river_geojson = _load_river_geojson()
                else:
                    river_geojson = generate_synthetic_river(
                        {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon},
                        name=f"{name} Waterway"
                    )

            return {
                "name": name,
                "region": region,
                "basin": payload.get("basin") or f"{name} Basin",
                "scope_note": payload.get("scope_note") or f"Request-scoped study area for {name}.",
                "state": state_name,
                "bounding_box": {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon},
                "center": {"lat": round(float(center["lat"]), 6), "lon": round(float(center["lon"]), 6)},
                "river": river_name,
                "reference_gauge": payload.get("reference_gauge") or f"{name} Virtual Gauge",
                "reference_gauge_coords": center,
                "reference_gauge_source": payload.get("reference_gauge_source") or "Request-scoped virtual gauge",
                "river_geojson": river_geojson,
                "is_default_location": _is_vijayawada_location(center["lat"], center["lon"]),
            }

    # Case 2: Explicit location query or coordinates
    if location_query or (latitude is not None and longitude is not None):
        res = select_study_area(
            location_query=location_query,
            latitude=latitude,
            longitude=longitude,
            half_size_deg=half_size_deg,
            study_area_polygon=study_area_polygon,
            set_as_active=False,
        )
        if res.get("status") == "OK" and "study_area" in res:
            sa = dict(res["study_area"])
            sa["is_default_location"] = res.get("is_default_location", False)
            return sa

    # Case 3: In strict multi-user mode without fallback, reject missing context
    if not allow_fallback:
        raise ValueError(
            "Missing required study area context in multi-user mode. "
            "Please provide 'study_area', 'analysis_id', or explicitly set 'use_benchmark=True'."
        )

    # Case 4: Legacy backward compatibility fallback
    active = get_active_area()
    if active:
        sa = dict(active)
        sa["is_default_location"] = False
        return sa

    # Case 5: Default Vijayawada study area (legacy fallback)
    sa = dict(STUDY_AREA)
    sa["is_default_location"] = True
    return sa


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
        "tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "tile_subdomains": [],
        "tile_attribution": 'Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, METI, TomTom',
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
