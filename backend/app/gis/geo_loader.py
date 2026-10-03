"""
GIS Geo Loader
==============
Provides the geographic layers for the study area:
 - study area boundary (rectangular bounding region - see docstring below)
 - river centerline, loaded from a local project-managed GeoJSON file
 - flood-risk zone grid (modelled grid geometry, labelled MODELLED_GRID)

DATA SOURCE & RESOLUTION (documented, honest):
  - Boundary: a rectangular bounding region around the Vijayawada-Krishna
    corridor. This is NOT an official administrative or hydrological
    boundary polygon - it is a project-defined geographic frame used to scope the
    classical system's map and zone grid.
  - River: loaded from `data/geo/krishna_river.geojson`, a hand-authored
    28-vertex polyline referenced against the river's publicly known course
    through Vijayawada. Documented resolution limitations are recorded in
    that file's `metadata` block. Swapping in an authoritative CWC/KGBO/
    Survey-of-India GeoJSON later requires only replacing that file - every
    downstream consumer here reads the same GeoJSON Feature shape.
  - Risk zones: a deterministic rectangular grid ("MODELLED_GRID" spatial
    model), clipped to the study-area bounding box. Zone risk itself comes
    from actual system logic (risk_engine), never from the grid geometry.
"""
import json
from app.config.settings import STUDY_AREA, DATA_GEO_DIR, RISK_ZONE_RESOLUTIONS
from app.gis.distance_utils import build_river_linestring, distance_to_river_km

_river_geojson_cache = None
_river_linestring_cache = None


def _load_river_geojson() -> dict:
    global _river_geojson_cache
    if _river_geojson_cache is None:
        path = DATA_GEO_DIR / "krishna_river.geojson"
        with open(path, "r") as f:
            collection = json.load(f)
        _river_geojson_cache = collection["features"][0]
    return _river_geojson_cache


def get_river_linestring():
    """Public accessor for the cached shapely LineString of the river
    geometry, reusable by other modules (e.g. optimization.candidate_generator)
    that need real geometry-aware calculations against the river."""
    global _river_linestring_cache
    if _river_linestring_cache is None:
        _river_linestring_cache = build_river_linestring(_load_river_geojson())
    return _river_linestring_cache


def get_study_area_boundary() -> dict:
    bbox = STUDY_AREA["bounding_box"]
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
            "name": STUDY_AREA["name"],
            "region": STUDY_AREA["region"],
            "boundary_type": "RECTANGULAR_SCOPING_FRAME",
        },
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }


def get_river_centerline() -> dict:
    """Returns the river as a GeoJSON Feature, loaded from the local
    project-managed GeoJSON dataset (see module docstring for provenance)."""
    return _load_river_geojson()


def get_risk_zone_geometry(resolution: str = "default") -> list:
    """
    Returns a deterministic NxN grid of sub-zones covering the study area
    bounding box (MODELLED_GRID spatial model - documented, not an official
    flood-zone polygon set). `resolution` controls the grid granularity:
      "low"     -> 4x4  = 16 zones  (coarse, fast)
      "default" -> 6x6  = 36 zones  (balanced)
      "high"    -> 10x10 = 100 zones (finer analysis for experiments)
    Each zone gets a stable ID and a real distance-to-river measurement in
    kilometres, computed against the nearest point on the actual river
    LineString geometry (not a crude degree difference, not limited to
    comparing against a few waypoints - see gis.distance_utils.distance_to_river_km).
    """
    if resolution not in RISK_ZONE_RESOLUTIONS:
        resolution = "default"
    bbox = STUDY_AREA["bounding_box"]
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
