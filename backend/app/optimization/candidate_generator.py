"""
CandidateGenerator
===================
Generates candidate sensor locations deterministically from the study
area's zone geometry - NOT random map points.

Method (documented):
  For every risk zone (from gis.geo_loader.get_risk_zone_geometry), we place
  ONE candidate location at the zone centroid, plus - for zones within
  NEAR_RIVER_KM of the river - a SECOND candidate that is genuinely moved
  toward the river:

    1. Find the nearest point on the actual river LineString geometry to
       the zone centroid (gis.distance_utils.direction_to_river).
    2. Move the candidate CANDIDATE_RIVER_PULL_FRACTION of the way from the
       centroid toward that nearest point (a real direction vector computed
       from geometry, not a fixed southwest offset).
    3. Clamp the resulting point to stay within the study-area bounding box.

This mirrors real deployment practice: monitoring stations are sited to
represent each administrative sub-zone, with extra density along the
riverbank where flood exposure concentrates - and the "toward the river"
claim is now backed by an actual geometric calculation.

Each candidate carries a `risk_weight` derived from the zone's current risk
score (from risk_engine) so the optimiser maximises *risk-weighted*
coverage, not just geometric coverage.
"""
from app.gis.geo_loader import get_risk_zone_geometry, get_river_linestring
from app.gis.distance_utils import direction_to_river
from app.config.settings import STUDY_AREA, CANDIDATE_RIVER_PULL_FRACTION

NEAR_RIVER_KM = 1.5  # kept consistent with risk/risk_engine.py's NEAR_RIVER_KM


def _clamp_to_study_area(lat: float, lon: float) -> tuple:
    bbox = STUDY_AREA["bounding_box"]
    clamped_lat = min(max(lat, bbox["min_lat"]), bbox["max_lat"])
    clamped_lon = min(max(lon, bbox["min_lon"]), bbox["max_lon"])
    return clamped_lat, clamped_lon


def generate_candidates(zone_risk_lookup: dict = None, resolution: str = "default") -> list:
    """
    zone_risk_lookup: optional {zone_id: risk_score} from risk_engine output.
    If not supplied, all zones get a neutral weight of 1.
    resolution: risk-zone grid resolution ("low"/"default"/"high") - must
    match the resolution used to produce zone_risk_lookup, if supplied.
    """
    zones = get_risk_zone_geometry(resolution)
    river_line = get_river_linestring()

    candidates = []
    cand_id = 0
    for z in zones:
        weight = 1
        if zone_risk_lookup and z["zone_id"] in zone_risk_lookup:
            weight = zone_risk_lookup[z["zone_id"]]

        centroid_lat, centroid_lon = z["centroid"]["lat"], z["centroid"]["lon"]
        is_near_river = z["distance_to_river_km"] < NEAR_RIVER_KM

        cand_id += 1
        candidates.append({
            "candidate_id": f"C-{cand_id:03d}",
            "lat": centroid_lat,
            "lon": centroid_lon,
            "zone_id": z["zone_id"],
            "risk_weight": weight,
            "near_river": is_near_river,
            "placement_method": "ZONE_CENTROID",
        })

        if is_near_river:
            direction = direction_to_river(centroid_lat, centroid_lon, river_line)
            # Linear interpolation between the centroid and the actual
            # nearest point on the river geometry - a real, geometry-derived
            # direction, not an arbitrary fixed offset.
            pulled_lat = centroid_lat + (direction["nearest_lat"] - centroid_lat) * CANDIDATE_RIVER_PULL_FRACTION
            pulled_lon = centroid_lon + (direction["nearest_lon"] - centroid_lon) * CANDIDATE_RIVER_PULL_FRACTION
            pulled_lat, pulled_lon = _clamp_to_study_area(pulled_lat, pulled_lon)

            cand_id += 1
            candidates.append({
                "candidate_id": f"C-{cand_id:03d}",
                "lat": pulled_lat,
                "lon": pulled_lon,
                "zone_id": z["zone_id"],
                "risk_weight": weight,
                "near_river": True,
                "placement_method": "PULLED_TOWARD_RIVER_GEOMETRY",
                "pulled_fraction": CANDIDATE_RIVER_PULL_FRACTION,
            })

    return candidates
