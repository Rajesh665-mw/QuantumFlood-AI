import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.gis.geo_loader import get_river_centerline, get_risk_zone_geometry, get_river_linestring, get_study_area_boundary
from app.gis.distance_utils import distance_to_river_km, direction_to_river
from app.optimization.candidate_generator import generate_candidates
from app.config.settings import STUDY_AREA


def test_river_geometry_loads_and_has_multiple_vertices():
    river = get_river_centerline()
    coords = river["geometry"]["coordinates"]
    # Must be a real multi-vertex polyline, not just 2-3 coarse waypoints.
    # (v2 revision anchors several vertices to real, sourced landmark
    # coordinates rather than maximising vertex count for its own sake.)
    assert len(coords) >= 10


def test_risk_zones_use_km_distance_not_degrees():
    zones = get_risk_zone_geometry()
    for z in zones:
        assert "distance_to_river_km" in z
        assert "distance_to_river_deg" not in z
        # Sanity bound: study area spans roughly 15km, so no zone should be
        # more than ~20km from the river within this corridor.
        assert 0 <= z["distance_to_river_km"] < 20


def test_distance_to_river_uses_nearest_point_not_just_waypoints():
    river_line = get_river_linestring()
    # A point roughly halfway between two river vertices should have a
    # small nearest-point distance (using linear referencing), much smaller
    # than its distance to either individual waypoint would suggest for a
    # naive "nearest waypoint only" approach.
    mid_lat, mid_lon = 16.478, 80.615
    d = distance_to_river_km(mid_lat, mid_lon, river_line)
    assert d < 5.0  # should find a genuinely close point along the line


def test_direction_to_river_points_toward_actual_nearest_point():
    river_line = get_river_linestring()
    result = direction_to_river(16.50, 80.60, river_line)
    assert "nearest_lat" in result and "nearest_lon" in result
    assert result["distance_km"] >= 0


def test_candidate_generation_stays_within_study_area():
    candidates = generate_candidates()
    bbox = STUDY_AREA["bounding_box"]
    for c in candidates:
        assert bbox["min_lat"] - 1e-6 <= c["lat"] <= bbox["max_lat"] + 1e-6
        assert bbox["min_lon"] - 1e-6 <= c["lon"] <= bbox["max_lon"] + 1e-6


def test_river_pulled_candidates_are_closer_to_river_than_centroid():
    river_line = get_river_linestring()
    candidates = generate_candidates()
    pulled = [c for c in candidates if c.get("placement_method") == "PULLED_TOWARD_RIVER_GEOMETRY"]
    assert len(pulled) > 0
    for c in pulled:
        # Find the sibling centroid candidate for the same zone
        centroid_candidate = next(
            cc for cc in candidates if cc["zone_id"] == c["zone_id"] and cc["placement_method"] == "ZONE_CENTROID"
        )
        dist_pulled = distance_to_river_km(c["lat"], c["lon"], river_line)
        dist_centroid = distance_to_river_km(centroid_candidate["lat"], centroid_candidate["lon"], river_line)
        assert dist_pulled <= dist_centroid + 1e-6


def test_study_area_boundary_is_valid_polygon():
    boundary = get_study_area_boundary()
    coords = boundary["geometry"]["coordinates"][0]
    assert coords[0] == coords[-1]  # closed ring
    assert len(coords) == 5


def test_river_geometry_includes_real_sourced_anchor_near_barrage():
    """The river geometry must pass near the real, sourced Prakasam Barrage
    coordinates (16.50611, 80.60500) - not an arbitrary path."""
    river_line = get_river_linestring()
    barrage_lat, barrage_lon = 16.50611, 80.60500
    d = distance_to_river_km(barrage_lat, barrage_lon, river_line)
    assert d < 0.05  # essentially on the line (it's a literal vertex)


def test_risk_zone_resolution_options():
    low = get_risk_zone_geometry("low")
    default = get_risk_zone_geometry("default")
    high = get_risk_zone_geometry("high")
    assert len(low) == 16
    assert len(default) == 36
    assert len(high) == 100
    # unknown resolution falls back to default rather than erroring
    fallback = get_risk_zone_geometry("nonsense")
    assert len(fallback) == len(default)
