"""
RiskEngine
==========
Turns a single forecast (water level / inflow / rainfall) plus the study
area's zone geometry into a per-zone flood risk map.

Spatial Risk Model (MODELLED_SPATIAL_ATTENUATION):
  The forecast represents conditions at the reference gauge (Prakasam
  Barrage). Real flood impact diminishes with distance from the river.
  This model applies zone-specific attenuation:

  1. River proximity factor — exponential decay:
       proximity_factor = exp(-distance_km / DECAY_CONSTANT_KM)
     where DECAY_CONSTANT_KM controls how quickly influence falls off.
     At 0 km: factor ≈ 1.0 (full gauge reading applies).
     At ~3.5 km: factor ≈ 0.5.
     At >7 km: factor < 0.15 (very attenuated).

  2. Effective values per zone:
       effective_water_level = base_water_level × proximity_factor
       effective_inflow      = base_inflow × proximity_factor
       (rainfall is NOT attenuated — it falls everywhere, not just near
        the river, so it stays uniform across all zones.)

  3. Risk classification is then applied to each zone's EFFECTIVE values
     (not the raw uniform forecast), giving genuinely different risk
     levels across the study area.

  4. Each zone result includes a 'risk_factors' dict documenting exactly
     WHY it received its risk score — full factor breakdowns, no opaque
     numbers.

  This is an IMPROVEMENT over the previous model which applied a flat ±1
  risk band shift. It is still a modelled simplification (not measured
  per-zone water levels), but is physically more defensible and produces
  meaningful spatial variation. Documented as MODELLED_SPATIAL_ATTENUATION
  in the data provenance system.
"""
import math
from app.risk.risk_classifier import classify_risk, RISK_LEVELS, RISK_SCORE_MAP
from app.gis.geo_loader import get_risk_zone_geometry

# Decay constant controls the exponential fall-off of river influence.
# At distance = DECAY_CONSTANT_KM, the proximity factor ≈ 0.368 (1/e).
# Chosen so that zones within ~1.5 km get factor > 0.65 (strong influence),
# zones at ~3.5 km get factor ~0.5, and zones > 7 km get factor < 0.15.
DECAY_CONSTANT_KM = 3.5

# Proximity band labels (for human-readable factor breakdowns)
NEAR_RIVER_KM = 1.5
FAR_FROM_RIVER_KM = 4.0


def _proximity_factor(distance_km: float) -> float:
    """Exponential decay factor: 1.0 at river, → 0 with distance."""
    return math.exp(-distance_km / DECAY_CONSTANT_KM)


def _proximity_band(distance_km: float) -> str:
    if distance_km < NEAR_RIVER_KM:
        return "NEAR_RIVER"
    elif distance_km <= FAR_FROM_RIVER_KM:
        return "MID_RANGE"
    else:
        return "FAR_FROM_RIVER"


def generate_zone_risk_map(water_level_m: float, inflow_ktcmd: float, rainfall_mm_24h: float,
                            resolution: str = "default") -> dict:
    """Generate a per-zone risk map with zone-specific spatial attenuation."""

    # Base classification (uniform, at the gauge)
    base = classify_risk(water_level_m, inflow_ktcmd, rainfall_mm_24h)
    zones = get_risk_zone_geometry(resolution)

    zone_results = []
    for z in zones:
        dist_km = z["distance_to_river_km"]
        pf = _proximity_factor(dist_km)
        band = _proximity_band(dist_km)

        # Zone-specific effective values (spatial attenuation)
        # Rainfall is NOT attenuated — it falls uniformly, not from the river.
        eff_water_level = water_level_m * pf
        eff_inflow = inflow_ktcmd * pf

        # Classify risk using this zone's attenuated values
        zone_classification = classify_risk(eff_water_level, eff_inflow, rainfall_mm_24h)
        zone_level = zone_classification["overall_risk"]

        # Build factor breakdown for explainability
        risk_factors = {
            "river_proximity_factor": round(pf, 4),
            "effective_water_level_m": round(eff_water_level, 2),
            "effective_inflow_ktcmd": round(eff_inflow, 2),
            "base_water_level_m": round(water_level_m, 2),
            "base_inflow_ktcmd": round(inflow_ktcmd, 2),
            "rainfall_mm_24h": round(rainfall_mm_24h, 2),
            "distance_to_river_km": round(dist_km, 3),
            "proximity_band": band,
            "attenuation_model": "EXPONENTIAL_DECAY",
            "decay_constant_km": DECAY_CONSTANT_KM,
            "driving_factor": zone_classification["driving_factor"],
            "explanation": zone_classification["explanation"],
        }

        zone_results.append({
            "zone_id": z["zone_id"],
            "spatial_model": z["spatial_model"],
            "resolution": z["resolution"],
            "centroid": z["centroid"],
            "bounds": z["bounds"],
            "risk_level": zone_level,
            "risk_score": RISK_SCORE_MAP[zone_level],
            "distance_to_river_km": dist_km,
            "risk_factors": risk_factors,
        })

    return {
        "base_classification": base,
        "zones": zone_results,
        "resolution": resolution,
        "critical_zone_count": sum(1 for z in zone_results if z["risk_level"] == "CRITICAL"),
        "high_zone_count": sum(1 for z in zone_results if z["risk_level"] == "HIGH"),
        "spatial_model": {
            "type": "MODELLED_SPATIAL_ATTENUATION",
            "method": "EXPONENTIAL_DECAY",
            "decay_constant_km": DECAY_CONSTANT_KM,
            "near_river_km": NEAR_RIVER_KM,
            "far_from_river_km": FAR_FROM_RIVER_KM,
            "description": (
                f"Zone-specific risk via exponential proximity attenuation: "
                f"river-gauge forecast values are multiplied by exp(-distance/{DECAY_CONSTANT_KM}) "
                f"for water level and inflow (rainfall is uniform). "
                f"Zones within {NEAR_RIVER_KM}km are NEAR_RIVER (high exposure); "
                f"zones beyond {FAR_FROM_RIVER_KM}km are FAR_FROM_RIVER (low exposure)."
            ),
            "note": "This is a modelled spatial simplification, not measured per-zone water levels.",
        },
        # Backward compatibility: keep proximity_rule for existing frontend
        "proximity_rule": {
            "near_river_km": NEAR_RIVER_KM,
            "far_from_river_km": FAR_FROM_RIVER_KM,
            "description": (
                f"Zone-specific spatial attenuation (exponential decay, constant={DECAY_CONSTANT_KM}km): "
                f"zones near the river experience higher effective flood values; "
                f"zones far from the river are attenuated."
            ),
        },
    }
