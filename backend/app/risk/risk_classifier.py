"""
Rule-based risk classifier. Converts a water level / inflow / rainfall
reading into a documented risk category using the thresholds defined in
app.config.settings.RISK_THRESHOLDS. No randomness anywhere in this module.
"""
from app.config.settings import RISK_THRESHOLDS

RISK_LEVELS = ["LOW", "MODERATE", "HIGH", "CRITICAL"]
RISK_SCORE_MAP = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}


def _classify_single(value: float, thresholds: dict) -> str:
    if value >= thresholds["high"]:
        return "CRITICAL"
    if value >= thresholds["moderate"]:
        return "HIGH"
    if value >= thresholds["low"]:
        return "MODERATE"
    return "LOW"


def classify_risk(water_level_m: float, inflow_ktcmd: float, rainfall_mm_24h: float) -> dict:
    """
    Combines three threshold-based sub-classifications by taking the MAXIMUM
    (worst-case) severity across water level, inflow, and rainfall, which is
    the documented conservative rule used for disaster-response prioritisation.
    """
    wl_level = _classify_single(water_level_m, RISK_THRESHOLDS["water_level_m"])
    inflow_level = _classify_single(inflow_ktcmd, RISK_THRESHOLDS["inflow_ktcmd"])
    rain_level = _classify_single(rainfall_mm_24h, RISK_THRESHOLDS["rainfall_mm_24h"])

    levels = {"water_level_m": wl_level, "inflow_ktcmd": inflow_level, "rainfall_mm_24h": rain_level}
    overall = max(levels.values(), key=lambda lvl: RISK_SCORE_MAP[lvl])

    driver = max(levels, key=lambda k: RISK_SCORE_MAP[levels[k]])
    threshold_used = RISK_THRESHOLDS[driver]
    # Build a clear, factual explanation string
    value_lookup = {"water_level_m": water_level_m, "inflow_ktcmd": inflow_ktcmd, "rainfall_mm_24h": rainfall_mm_24h}
    driver_value = value_lookup[driver]
    driver_label = driver.replace('_', ' ')

    if overall == "CRITICAL":
        # CRITICAL is classified as >= the 'high' threshold; there is no separate
        # 'critical' key in the threshold dict. Make this clear in the explanation.
        reason = (
            f"Driven by {driver_label} = {driver_value:.2f}, which exceeds the highest "
            f"threshold (≥ {threshold_used['high']} for this parameter), placing it in the "
            f"CRITICAL risk band."
        )
    else:
        # Map each risk level to the threshold key that starts its band:
        #   _classify_single maps: >= 'low' → MODERATE, >= 'moderate' → HIGH
        #   So MODERATE band starts at threshold['low'], HIGH starts at threshold['moderate']
        band_start_key = {"MODERATE": "low", "HIGH": "moderate", "LOW": None}
        start_key = band_start_key.get(overall)
        if start_key and start_key in threshold_used:
            threshold_value = threshold_used[start_key]
            reason = (
                f"Driven by {driver_label} = {driver_value:.2f}, which falls in the "
                f"{overall} band (≥ {threshold_value} for this parameter)."
            )
        else:
            # LOW: below all thresholds
            reason = (
                f"Driven by {driver_label} = {driver_value:.2f}, which falls below "
                f"all risk thresholds (< {threshold_used['low']} for this parameter)."
            )

    return {
        "overall_risk": overall,
        "risk_score": RISK_SCORE_MAP[overall],
        "component_levels": levels,
        "driving_factor": driver,
        "explanation": reason,
    }
