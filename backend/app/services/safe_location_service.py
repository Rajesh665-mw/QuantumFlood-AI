"""
Risk-Aware Safe Location Finder Service
=======================================
Evaluates candidate public facilities and potential assembly sites across the
Vijayawada–Krishna River Corridor to identify locations with comparatively
lower flood risk.

Methodology (Transparent Multi-Criteria Decision Analysis - MCDA):
  1. River Proximity & Flood Risk: Zone-level modelled flood risk + great-circle
     standoff distance from the river geometry.
  2. Topographic Elevation: Higher ground elevation from SRTM survey estimates.
  3. Accessibility: Road class connectivity (National Highway, Primary Arterial, etc.).
  4. Configurable Weights: Weights are normalized and user-tunable.

Scientific Honesty & Terminology Policy:
  - Locations are strictly termed "Lower-Risk Locations" or "Recommended Locations",
    NEVER "guaranteed safe".
  - Capacities are explicitly marked UNAVAILABLE / NOT SURVEYED.
  - Results serve as research decision-support, not official government warnings.
"""
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config.settings import DATA_GEO_DIR
from app.gis.geo_loader import get_river_linestring
from app.gis.distance_utils import distance_to_river_km
from app.utils.geo_math import haversine_km

logger = logging.getLogger(__name__)

ROAD_CLASS_WEIGHTS = {
    "NATIONAL_HIGHWAY": 1.0,
    "PRIMARY_ARTERIAL": 0.85,
    "MAJOR_CITY_ARTERIAL": 0.80,
    "ELEVATED_FLYOVER": 0.75,
    "SECONDARY_ARTERIAL": 0.65,
    "CITY_ARTERIAL": 0.60,
    "SECONDARY_ROAD": 0.45,
    "RIVERFRONT_ROAD": 0.30,
}

_safe_locations_cache = None


def load_candidate_safe_locations() -> List[Dict[str, Any]]:
    """Loads the candidate facilities dataset from data/geo/safe_locations.json."""
    global _safe_locations_cache
    if _safe_locations_cache is None:
        path = DATA_GEO_DIR / "safe_locations.json"
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _safe_locations_cache = data.get("features", [])
    return _safe_locations_cache


def _find_zone_for_point(lat: float, lon: float, zones: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Finds the containing grid zone or the nearest zone centroid."""
    if not zones:
        return None
    for z in zones:
        b = z["bounds"]
        if b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]:
            return z

    # Fallback to nearest centroid if slightly beyond boundary edge
    closest_zone = min(
        zones,
        key=lambda z: haversine_km(lat, lon, z["centroid"]["lat"], z["centroid"]["lon"])
    )
    return closest_zone


def evaluate_safe_locations(
    zones: List[Dict[str, Any]],
    weight_elevation: float = 0.25,
    weight_risk: float = 0.35,
    weight_distance: float = 0.20,
    weight_accessibility: float = 0.20,
    min_elevation_m: Optional[float] = None,
    max_risk_level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates candidate locations against the current active risk map.
    Returns normalized ranking scores, factor breakdowns, and transparent explanations.
    """
    candidates = load_candidate_safe_locations()
    if not candidates:
        return {
            "locations": [],
            "total_candidates": 0,
            "weights_used": {
                "elevation": weight_elevation,
                "risk": weight_risk,
                "distance_to_risk": weight_distance,
                "accessibility": weight_accessibility
            },
            "disclaimer": "No candidate locations available."
        }

    total_weight = weight_elevation + weight_risk + weight_distance + weight_accessibility
    if total_weight <= 0:
        weight_elevation = weight_risk = weight_distance = weight_accessibility = 0.25
        total_weight = 1.0

    w_elev = weight_elevation / total_weight
    w_risk = weight_risk / total_weight
    w_dist = weight_distance / total_weight
    w_access = weight_accessibility / total_weight

    river_line = get_river_linestring()

    evaluated = []
    elevations = []
    distances = []
    risks = []
    accessibilities = []

    risk_rank = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}

    for feat in candidates:
        props = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]

        zone = _find_zone_for_point(lat, lon, zones)
        zone_id = zone.get("zone_id", "Z-UNKNOWN") if zone else "Z-UNKNOWN"
        risk_level = zone.get("risk_level", "LOW") if zone else "LOW"
        risk_score = zone.get("risk_score", 1) if zone else 1

        dist_river = distance_to_river_km(lat, lon, river_line)
        elev = float(props.get("elevation_m", 20.0))
        road_class = props.get("road_class", "CITY_ARTERIAL")
        access_score = ROAD_CLASS_WEIGHTS.get(road_class, 0.5)

        # Filters
        if min_elevation_m is not None and elev < min_elevation_m:
            continue
        if max_risk_level is not None and risk_rank.get(risk_level, 1) > risk_rank.get(max_risk_level, 4):
            continue

        elevations.append(elev)
        distances.append(dist_river)
        risks.append(risk_score)
        accessibilities.append(access_score)

        evaluated.append({
            "id": props["id"],
            "name": props["name"],
            "category": props.get("category", "PUBLIC_FACILITY"),
            "lat": lat,
            "lon": lon,
            "elevation_m": round(elev, 1),
            "distance_to_river_km": round(dist_river, 2),
            "assigned_zone_id": zone_id,
            "modelled_risk_level": risk_level,
            "risk_score": risk_score,
            "primary_road_access": props.get("primary_road_access", "Local Access"),
            "road_class": road_class,
            "accessibility_score": access_score,
            "capacity_surveyed": props.get("capacity_surveyed", False),
            "capacity_status": props.get("capacity_status", "UNAVAILABLE"),
            "raw_notes": props.get("notes", ""),
        })

    if not evaluated:
        return {
            "locations": [],
            "total_candidates": len(candidates),
            "weights_used": {
                "elevation": round(w_elev, 3),
                "risk": round(w_risk, 3),
                "distance_to_risk": round(w_dist, 3),
                "accessibility": round(w_access, 3),
            },
            "disclaimer": "All candidate locations were filtered out by current criteria."
        }

    min_elev, max_elev = min(elevations), max(elevations)
    elev_range = (max_elev - min_elev) if max_elev > min_elev else 1.0

    min_dist, max_dist = min(distances), max(distances)
    dist_range = (max_dist - min_dist) if max_dist > min_dist else 1.0

    min_r, max_r = 1, 4
    r_range = 3.0

    min_acc, max_acc = min(accessibilities), max(accessibilities)
    acc_range = (max_acc - min_acc) if max_acc > min_acc else 1.0

    results = []
    for loc in evaluated:
        norm_elev = (loc["elevation_m"] - min_elev) / elev_range
        # Lower risk score -> higher safety contribution
        norm_risk_safety = 1.0 - ((loc["risk_score"] - min_r) / r_range)
        norm_dist = (loc["distance_to_river_km"] - min_dist) / dist_range
        norm_access = (loc["accessibility_score"] - min_acc) / acc_range

        composite_score = (
            w_elev * norm_elev +
            w_risk * norm_risk_safety +
            w_dist * norm_dist +
            w_access * norm_access
        ) * 100.0

        score_val = round(composite_score, 1)

        explanation_parts = []
        if loc["modelled_risk_level"] in ("LOW", "MODERATE"):
            explanation_parts.append(f"comparatively lower modelled flood risk ({loc['modelled_risk_level']})")
        else:
            explanation_parts.append(f"elevated modelled risk ({loc['modelled_risk_level']}) in local zone")

        if loc["elevation_m"] >= 25.0:
            explanation_parts.append(f"higher topographic elevation ({loc['elevation_m']}m)")
        else:
            explanation_parts.append(f"moderate elevation ({loc['elevation_m']}m)")

        if loc["distance_to_river_km"] >= 3.0:
            explanation_parts.append(f"{loc['distance_to_river_km']} km standoff from river channel")

        explanation_parts.append(f"direct access via {loc['primary_road_access']}")

        explanation = (
            f"Recommended because it provides {' and '.join(explanation_parts)}. "
            f"Evaluated with MCDA Recommendation Score {score_val}/100."
        )

        results.append({
            **loc,
            "recommendation_score": score_val,
            "score_breakdown": {
                "elevation_contribution": round(w_elev * norm_elev * 100, 1),
                "low_risk_contribution": round(w_risk * norm_risk_safety * 100, 1),
                "distance_contribution": round(w_dist * norm_dist * 100, 1),
                "accessibility_contribution": round(w_access * norm_access * 100, 1),
            },
            "explanation": explanation,
            "status_label": "Recommended Lower-Risk Location" if score_val >= 60 else "Secondary Consideration",
        })

    results.sort(key=lambda x: x["recommendation_score"], reverse=True)

    return {
        "locations": results,
        "total_candidates": len(candidates),
        "total_recommended": len(results),
        "weights_used": {
            "elevation": round(w_elev, 3),
            "risk": round(w_risk, 3),
            "distance_to_risk": round(w_dist, 3),
            "accessibility": round(w_access, 3),
        },
        "scientific_honesty_note": (
            "Model-based recommendation using open geographic data and flood simulation. "
            "Locations are comparatively lower-risk based on modelled factors. "
            "Structural shelter safety, emergency supplies, and capacity are NOT surveyed."
        )
    }
