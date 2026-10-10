"""
GIS Geo Loader
==============
Provides the geographic layers for the study area:
 - study area boundary (rectangular bounding region - see docstring below)
 - river centerline, loaded from a local project-managed GeoJSON file
 - flood-risk zone grid (modelled grid geometry, labelled MODELLED_GRID)

GENERALIZATION NOTE (v2.0):
  This module now supports dynamic study areas selected at runtime.
  When an active area is set via the area selection API, all functions
  read from the dynamic area configuration instead of the hardcoded
  Vijayawada defaults. The default (Vijayawada) study area remains the
  fallback when no dynamic area is active.

DATA SOURCE & RESOLUTION (documented, honest):
  - Boundary: a rectangular bounding region around the study area.
    This is NOT an official administrative or hydrological boundary
    polygon - it is a project-defined geographic frame used to scope the
    system's map and zone grid.
  - River: loaded from `data/geo/krishna_river.geojson` for the default
    Vijayawada study area, or dynamically fetched from OpenStreetMap for
    custom areas. Data provenance is tracked per-location.
  - Risk zones: a deterministic rectangular grid ("MODELLED_GRID" spatial
    model), clipped to the study-area bounding box. Zone risk itself comes
    from actual system logic (risk_engine), never from the grid geometry.
"""
import json
from shapely.geometry import LineString, Point
from app.config.settings import STUDY_AREA, DATA_GEO_DIR, RISK_ZONE_RESOLUTIONS
from app.gis.distance_utils import build_river_linestring, distance_to_river_km
from app.services.active_area import (
    get_active_area,
    get_active_bounding_box,
    get_active_river_geojson,
    is_default_area,
)

_river_geojson_cache = None
_river_linestring_cache = None

# Cache for dynamically-built river linestrings (keyed by area identity)
_dynamic_river_linestring_cache = None
_dynamic_river_area_key = None


def _load_river_geojson() -> dict:
    """Loads the default (Vijayawada/Krishna) river GeoJSON from disk."""
    global _river_geojson_cache
    if _river_geojson_cache is None:
        path = DATA_GEO_DIR / "krishna_river.geojson"
        with open(path, "r") as f:
            collection = json.load(f)
        _river_geojson_cache = collection["features"][0]
    return _river_geojson_cache


def _get_effective_river_geojson() -> dict:
    """Returns the river GeoJSON for the currently active area."""
    if is_default_area():
        return _load_river_geojson()
    dynamic_river = get_active_river_geojson()
    if dynamic_river is not None:
        return dynamic_river
    # Fallback to default if dynamic area has no river
    return _load_river_geojson()


def _get_effective_bbox() -> dict:
    """Returns the bounding box for the currently active area."""
    dynamic_bbox = get_active_bounding_box()
    if dynamic_bbox is not None:
        return dynamic_bbox
    return STUDY_AREA["bounding_box"]


def _get_effective_study_area() -> dict:
    """Returns the full study area config for the currently active area."""
    active = get_active_area()
    if active is not None:
        return active
    return STUDY_AREA


def get_river_linestring():
    """Public accessor for the cached shapely LineString of the river
    geometry, reusable by other modules (e.g. optimization.candidate_generator)
    that need real geometry-aware calculations against the river.

    Returns the linestring for the currently active area (dynamic or default).
    """
    global _river_linestring_cache
    global _dynamic_river_linestring_cache, _dynamic_river_area_key

    if is_default_area():
        if _river_linestring_cache is None:
            _river_linestring_cache = build_river_linestring(_load_river_geojson())
        return _river_linestring_cache

    # Dynamic area: check if cached linestring matches current area
    active = get_active_area()
    area_key = id(active) if active else None
    if _dynamic_river_linestring_cache is not None and _dynamic_river_area_key == area_key:
        return _dynamic_river_linestring_cache

    river_geojson = _get_effective_river_geojson()
    _dynamic_river_linestring_cache = build_river_linestring(river_geojson)
    _dynamic_river_area_key = area_key
    return _dynamic_river_linestring_cache


def get_study_area_boundary() -> dict:
    """Returns the study area boundary as a GeoJSON Feature (Polygon).

    Uses the currently active area (dynamic or default Vijayawada).
    """
    bbox = _get_effective_bbox()
    study_area = _get_effective_study_area()

    # Rectangular boundary polygon - a scoping frame for the prototype, not
    # an official administrative/hydrological boundary (see module docstring).
    coords = [
        [bbox["min_lon"], bbox["min_lat"]],
        [bbox["max_lon"], bbox["min_lat"]],
        [bbox["max_lon"], bbox["max_lat"]],
        [bbox["min_lon"], bbox["max_lat"]],
        [bbox["min_lon"], bbox["min_lat"]],
    ]
    return {
        "type": "Feature",
        "properties": {
            "name": study_area.get("name", "Study Area"),
            "region": study_area.get("region", ""),
            "boundary_type": "RECTANGULAR_SCOPING_FRAME",
        },
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }


def get_river_centerline() -> dict:
    """Returns the river as a GeoJSON Feature for the active area.

    For the default (Vijayawada) area, this comes from the local
    project-managed GeoJSON. For dynamic areas, it may come from
    OSM or be a synthetic centerline.
    """
    return _get_effective_river_geojson()


def get_risk_zone_geometry(resolution: str = "default") -> list:
    """
    Returns a deterministic NxN grid of sub-zones covering the active study
    area bounding box (MODELLED_GRID spatial model - documented, not an official
    flood-zone polygon set). `resolution` controls the grid granularity:
      "low"     -> 4x4  = 16 zones  (coarse, fast)
      "default" -> 6x6  = 36 zones  (balanced)
      "high"    -> 10x10 = 100 zones (finer analysis for experiments)

    Uses the currently active area (dynamic or default Vijayawada).
    Each zone gets a stable ID and a real distance-to-river measurement in
    kilometres, computed against the nearest point on the actual river
    LineString geometry (not a crude degree difference, not limited to
    comparing against a few waypoints - see gis.distance_utils.distance_to_river_km).
    """
    if resolution not in RISK_ZONE_RESOLUTIONS:
        resolution = "default"
    bbox = _get_effective_bbox()
    n = RISK_ZONE_RESOLUTIONS[resolution]
    lat_step = (bbox["max_lat"] - bbox["min_lat"]) / n
    lon_step = (bbox["max_lon"] - bbox["min_lon"]) / n

    river_line = get_river_linestring()

    zones = []
    zone_idx = 0
    for i in range(n):
        for j in range(n):
            min_lat = bbox["min_lat"] + i * lat_step
            max_lat = min_lat + lat_step
            min_lon = bbox["min_lon"] + j * lon_step
            max_lon = min_lon + lon_step
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2
            zone_idx += 1
            zones.append({
                "zone_id": f"Z-{zone_idx:03d}",
                "spatial_model": "MODELLED_GRID",
                "resolution": resolution,
                "grid_size": n,
                "bounds": {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon},
                "centroid": {"lat": center_lat, "lon": center_lon},
                "distance_to_river_km": round(distance_to_river_km(center_lat, center_lon, river_line), 3),
            })
    return zones
