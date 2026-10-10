"""
Geospatial Service — OSM Feature Fetching
==========================================
Fetches geographic features (water bodies, rivers) from OpenStreetMap via
the Overpass API for dynamically selected study areas.

This service:
  - Uses the public Overpass API (free, no API key)
  - Fetches waterways (rivers, streams, canals) within a bounding box
  - Converts results to GeoJSON format compatible with existing river layers
  - Implements caching, timeouts, and graceful fallbacks
  - Clearly labels data provenance (REAL/DERIVED/UNAVAILABLE)

Reference: https://wiki.openstreetmap.org/wiki/Overpass_API
"""
import logging
import urllib.request
import urllib.parse
import urllib.error
import json
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OVERPASS_TIMEOUT = 3  # seconds (short timeout to prevent UI hanging when upstream is congested)

# In-memory cache keyed by bounding box string
_feature_cache: Dict[str, Dict[str, Any]] = {}


def _make_bbox_key(bbox: dict) -> str:
    """Creates a cache key from a bounding box dict."""
    return f"{bbox['min_lat']:.4f},{bbox['min_lon']:.4f},{bbox['max_lat']:.4f},{bbox['max_lon']:.4f}"


def fetch_waterways(bbox: dict) -> Optional[Dict[str, Any]]:
    """
    Fetches waterway features (rivers, streams, canals) within the given
    bounding box from OpenStreetMap Overpass API.

    Args:
        bbox: {"min_lat": ..., "max_lat": ..., "min_lon": ..., "max_lon": ...}

    Returns:
        GeoJSON FeatureCollection with waterway LineString features,
        or None if the query fails.
    """
    cache_key = f"water_{_make_bbox_key(bbox)}"
    if cache_key in _feature_cache:
        logger.debug("Overpass cache hit for waterways: %s", cache_key)
        return _feature_cache[cache_key]

    # Overpass QL query for waterways in bounding box
    # Focus on named rivers and significant waterways
    overpass_query = f"""
    [out:json][timeout:{_OVERPASS_TIMEOUT}];
    (
      way["waterway"="river"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
      way["waterway"="canal"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
      way["waterway"="stream"]["name"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
      relation["waterway"="river"]({bbox['min_lat']},{bbox['min_lon']},{bbox['max_lat']},{bbox['max_lon']});
    );
    out body;
    >;
    out skel qt;
    """

    try:
        encoded = urllib.parse.urlencode({"data": overpass_query})
        req = urllib.request.Request(
            _OVERPASS_URL,
            data=encoded.encode("utf-8"),
            headers={"User-Agent": "QuantumFloodAI/2.0 (academic-research-project)"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning("Overpass API error fetching waterways: %s", e)
        _feature_cache[cache_key] = None
        return None

    # Convert Overpass JSON to GeoJSON
    geojson = _overpass_to_geojson(raw)
    _feature_cache[cache_key] = geojson
    return geojson


def _overpass_to_geojson(overpass_data: dict) -> Dict[str, Any]:
    """
    Converts Overpass API JSON response to a GeoJSON FeatureCollection
    containing LineString features for waterways.
    """
    elements = overpass_data.get("elements", [])

    # Build node lookup
    node_map = {}
    for el in elements:
        if el["type"] == "node":
            node_map[el["id"]] = (el["lon"], el["lat"])

    # Build way features
    features = []
    for el in elements:
        if el["type"] != "way":
            continue
        tags = el.get("tags", {})
        if "waterway" not in tags:
            continue

        # Resolve node references to coordinates
        coords = []
        for node_id in el.get("nodes", []):
            if node_id in node_map:
                coords.append(list(node_map[node_id]))

        if len(coords) < 2:
            continue

        waterway_name = tags.get("name") or tags.get("name:en") or tags.get("int_name") or tags.get("alt_name") or "Unnamed waterway"
        feature = {
            "type": "Feature",
            "properties": {
                "name": waterway_name,
                "waterway": tags.get("waterway", "river"),
                "osm_id": el["id"],
                "is_synthetic": False,
                "data_source": "REAL",
                "source": "OpenStreetMap / Overpass API",
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def get_primary_waterway(bbox: dict) -> Optional[Dict[str, Any]]:
    """
    Returns the single longest/most significant waterway feature within the
    bounding box, suitable for use as the 'river' layer in the existing
    GIS pipeline. Prioritizes explicitly named waterways over unnamed segments.
    Falls back gracefully to None.

    Returns a single GeoJSON Feature (not FeatureCollection).
    """
    collection = fetch_waterways(bbox)
    if not collection or not collection.get("features"):
        return None

    features = collection["features"]
    def score(f):
        name = f.get("properties", {}).get("name", "")
        has_real_name = 1 if (name and name != "Unnamed waterway") else 0
        coords_len = len(f.get("geometry", {}).get("coordinates", []))
        return (has_real_name, coords_len)

    best = max(features, key=score)
    return best


def generate_synthetic_river(bbox: dict, name: str = "Synthetic Demonstration River") -> Dict[str, Any]:
    """
    Generates a synthetic river centerline through the study area when
    real waterway data is unavailable. The river runs roughly through
    the center of the bounding box.

    This is CLEARLY LABELLED as SIMULATED and SYNTHETIC so it is never
    confused with or misrepresented as observed geography.
    """
    center_lat = (bbox["min_lat"] + bbox["max_lat"]) / 2
    center_lon = (bbox["min_lon"] + bbox["max_lon"]) / 2
    lat_span = bbox["max_lat"] - bbox["min_lat"]
    lon_span = bbox["max_lon"] - bbox["min_lon"]

    # Create a gentle S-curve through the study area
    import math
    num_points = 20
    coords = []
    for i in range(num_points):
        t = i / (num_points - 1)
        lon = bbox["min_lon"] + t * lon_span
        # Sinusoidal offset from center
        lat_offset = 0.15 * lat_span * math.sin(t * 2 * math.pi)
        lat = center_lat + lat_offset
        coords.append([round(lon, 6), round(lat, 6)])

    return {
        "type": "Feature",
        "properties": {
            "name": name,
            "waterway": "river",
            "is_synthetic": True,
            "data_source": "SIMULATED",
            "provenance": "SYNTHETIC_FALLBACK",
            "source": "Synthetic river centerline generated for demonstration (no live OSM waterway detected)",
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coords,
        },
    }


def assess_data_availability(bbox: dict, has_waterways: Optional[bool] = None) -> Dict[str, Dict[str, str]]:
    """
    Assesses what geographic data is available for the given bounding box.
    Returns a provenance dict compatible with the existing DATA_PROVENANCE
    format.
    """
    if has_waterways is None:
        waterways = fetch_waterways(bbox)
        has_waterways = waterways is not None and len(waterways.get("features", [])) > 0

    availability = {
        "geographic_boundary": {
            "status": "REAL",
            "reason": "Study area boundary generated from geocoded coordinates.",
        },
        "river_geometry": {
            "status": "REAL" if has_waterways else "SIMULATED",
            "reason": (
                "Real waterway geometry from OpenStreetMap Overpass API."
                if has_waterways else
                "No waterway data available from OpenStreetMap for this area. "
                "A synthetic river centerline is used for spatial attenuation modelling."
            ),
        },
        "study_area_boundary": {
            "status": "PROJECT_DEFINED",
            "reason": "Rectangular bounding region generated around the selected location.",
        },
        "risk_zones": {
            "status": "MODELLED_SPATIAL",
            "reason": (
                "Deterministic grid spatial model with exponential-decay spatial "
                "attenuation from the nearest waterway. Risk scoring uses documented, "
                "rule-based thresholds — not random assignment."
            ),
        },
        "rainfall_mm": {
            "status": "SIMULATED_INPUT",
            "reason": "Deterministic, seeded synthetic series. No live weather feed integrated for this location.",
        },
        "water_level_m": {
            "status": "SIMULATED_INPUT",
            "reason": "Deterministic, seeded synthetic series. No live gauge feed integrated for this location.",
        },
        "inflow_ktcmd": {
            "status": "SIMULATED_INPUT",
            "reason": "Deterministic, seeded synthetic series. No live discharge feed integrated for this location.",
        },
        "historical_flood_events": {
            "status": "UNAVAILABLE",
            "reason": "No sourced historical flood event data available for this location.",
        },
        "safe_candidate_locations": {
            "status": "UNAVAILABLE",
            "reason": "No pre-surveyed safe location candidates available for this area.",
        },
        "road_network": {
            "status": "UNAVAILABLE",
            "reason": "No pre-built road network graph available for this area. Evacuation routing requires location-specific road data.",
        },
    }

    return availability
