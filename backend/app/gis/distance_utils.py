"""
Geospatial Distance Utilities
==============================
Provides proper geometry-aware distance calculations against the river
LineString, replacing naive raw-degree Euclidean distance.

Method (documented):
  1. Build a shapely LineString from the river GeoJSON coordinates.
  2. For a given point, use LineString.project()/.interpolate() to find the
     NEAREST POINT on the river geometry (not just the nearest waypoint).
  3. Compute the real great-circle (haversine) distance in kilometres
     between the query point and that nearest point.

This is still a spherical-earth approximation (no full UTM/projected CRS),
which is an accepted simplification at this study-area scale (~15km across,
where the difference between spherical and projected distance is well under
1%), but it is a genuine geometry-aware calculation - not a crude degree
difference and not limited to comparing against a handful of waypoints.
"""
from shapely.geometry import LineString, Point
from app.utils.geo_math import haversine_km


def build_river_linestring(river_geojson: dict) -> LineString:
    coords = river_geojson["geometry"]["coordinates"]  # [[lon, lat], ...]
    return LineString(coords)


def nearest_point_on_river(lat: float, lon: float, river_line: LineString) -> tuple:
    """Returns (nearest_lat, nearest_lon) - the closest point ON the river
    geometry to the given (lat, lon), using shapely's linear-referencing
    projection (accurate for the LineString's own coordinate space)."""
    query_point = Point(lon, lat)  # shapely uses (x=lon, y=lat)
    distance_along_line = river_line.project(query_point)
    nearest = river_line.interpolate(distance_along_line)
    return nearest.y, nearest.x  # (lat, lon)


def distance_to_river_km(lat: float, lon: float, river_line: LineString) -> float:
    """Real great-circle distance (km) from (lat, lon) to the nearest point
    on the river geometry."""
    nearest_lat, nearest_lon = nearest_point_on_river(lat, lon, river_line)
    return haversine_km(lat, lon, nearest_lat, nearest_lon)


def direction_to_river(lat: float, lon: float, river_line: LineString) -> dict:
    """
    Returns the unit direction vector (in lat/lon degree space, adequate at
    this study-area scale) from (lat, lon) toward the nearest point on the
    river, plus the nearest point itself and the real distance in km.
    Used by candidate_generator to move a candidate a controlled distance
    TOWARD the actual river geometry - not a fixed, unrelated offset.
    """
    nearest_lat, nearest_lon = nearest_point_on_river(lat, lon, river_line)
    d_lat = nearest_lat - lat
    d_lon = nearest_lon - lon
    magnitude = (d_lat ** 2 + d_lon ** 2) ** 0.5
    if magnitude == 0:
        return {"unit_lat": 0.0, "unit_lon": 0.0, "nearest_lat": nearest_lat,
                "nearest_lon": nearest_lon, "distance_km": 0.0}
    return {
        "unit_lat": d_lat / magnitude,
        "unit_lon": d_lon / magnitude,
        "nearest_lat": nearest_lat,
        "nearest_lon": nearest_lon,
        "distance_km": haversine_km(lat, lon, nearest_lat, nearest_lon),
    }
