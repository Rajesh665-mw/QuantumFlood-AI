"""
Builds the coverage relationship between candidate sensor locations and
flood-risk zones, using real great-circle (haversine) distance - not
approximated or random logic.
"""
from app.utils.geo_math import haversine_km  # re-exported for existing imports


def build_coverage_matrix(candidates: list, zones: list, coverage_radius_km: float) -> dict:
    """
    Returns:
      {
        candidate_id: {
            "covered_zone_ids": [...],
            "weighted_coverage": float  # sum of risk_score for covered zones
        }, ...
      }
    Also returns zone_to_candidates for connectivity/gap analysis.
    """
    coverage = {}
    zone_to_candidates = {z["zone_id"]: [] for z in zones}

    for c in candidates:
        covered = []
        weighted = 0.0
        for z in zones:
            dist = haversine_km(c["lat"], c["lon"], z["centroid"]["lat"], z["centroid"]["lon"])
            if dist <= coverage_radius_km:
                covered.append(z["zone_id"])
                weighted += z["risk_score"]
                zone_to_candidates[z["zone_id"]].append(c["candidate_id"])
        coverage[c["candidate_id"]] = {
            "covered_zone_ids": covered,
            "weighted_coverage": weighted,
        }

    return {"candidate_coverage": coverage, "zone_to_candidates": zone_to_candidates}
