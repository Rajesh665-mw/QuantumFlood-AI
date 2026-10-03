import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.risk.risk_classifier import classify_risk


def test_low_risk():
    result = classify_risk(water_level_m=5.0, inflow_ktcmd=100.0, rainfall_mm_24h=10.0)
    assert result["overall_risk"] == "LOW"


def test_critical_risk_from_water_level():
    result = classify_risk(water_level_m=14.0, inflow_ktcmd=100.0, rainfall_mm_24h=10.0)
    assert result["overall_risk"] == "CRITICAL"
    assert result["driving_factor"] == "water_level_m"


def test_worst_case_rule_takes_max_severity():
    # inflow is CRITICAL, water level LOW -> overall must be CRITICAL (worst case)
    result = classify_risk(water_level_m=5.0, inflow_ktcmd=950.0, rainfall_mm_24h=10.0)
    assert result["overall_risk"] == "CRITICAL"
    assert result["driving_factor"] == "inflow_ktcmd"


def test_moderate_boundary():
    result = classify_risk(water_level_m=8.0, inflow_ktcmd=100.0, rainfall_mm_24h=10.0)
    assert result["overall_risk"] == "MODERATE"


# --- NEW: Spatial risk model tests ---

def test_zone_risk_map_returns_risk_factors():
    """Each zone in the risk map should include a risk_factors dict."""
    from app.risk.risk_engine import generate_zone_risk_map
    result = generate_zone_risk_map(12.0, 500.0, 60.0, "default")
    assert "zones" in result
    assert len(result["zones"]) > 0
    for zone in result["zones"]:
        assert "risk_factors" in zone
        rf = zone["risk_factors"]
        assert "river_proximity_factor" in rf
        assert "effective_water_level_m" in rf
        assert "proximity_band" in rf
        assert rf["attenuation_model"] == "EXPONENTIAL_DECAY"


def test_zone_risk_spatial_variation():
    """Zones near the river should have higher effective water levels than
    zones far from the river (spatial attenuation must produce variation)."""
    from app.risk.risk_engine import generate_zone_risk_map
    result = generate_zone_risk_map(12.0, 500.0, 60.0, "default")
    zones = result["zones"]

    eff_wl_values = [z["risk_factors"]["effective_water_level_m"] for z in zones]
    # There must be variation — not all the same value
    assert len(set(eff_wl_values)) > 1, "Spatial attenuation should produce varying effective water levels"

    # Near-river zones should have higher effective water levels
    near = [z for z in zones if z["risk_factors"]["proximity_band"] == "NEAR_RIVER"]
    far = [z for z in zones if z["risk_factors"]["proximity_band"] == "FAR_FROM_RIVER"]
    if near and far:
        avg_near = sum(z["risk_factors"]["effective_water_level_m"] for z in near) / len(near)
        avg_far = sum(z["risk_factors"]["effective_water_level_m"] for z in far) / len(far)
        assert avg_near > avg_far, "Near-river zones should have higher effective water levels"


def test_zone_risk_map_has_spatial_model():
    """The risk map output should include spatial_model metadata."""
    from app.risk.risk_engine import generate_zone_risk_map
    result = generate_zone_risk_map(12.0, 500.0, 60.0, "default")
    assert "spatial_model" in result
    assert result["spatial_model"]["type"] == "MODELLED_SPATIAL_ATTENUATION"
    assert result["spatial_model"]["method"] == "EXPONENTIAL_DECAY"


def test_zone_risk_proximity_factor_range():
    """Proximity factors should be in (0, 1] range."""
    from app.risk.risk_engine import generate_zone_risk_map
    result = generate_zone_risk_map(12.0, 500.0, 60.0, "default")
    for zone in result["zones"]:
        pf = zone["risk_factors"]["river_proximity_factor"]
        assert 0 < pf <= 1.0, f"Proximity factor {pf} out of valid range for {zone['zone_id']}"


def test_rainfall_not_attenuated():
    """Rainfall should be the same for all zones (not spatially attenuated)."""
    from app.risk.risk_engine import generate_zone_risk_map
    rainfall = 75.0
    result = generate_zone_risk_map(12.0, 500.0, rainfall, "default")
    for zone in result["zones"]:
        assert zone["risk_factors"]["rainfall_mm_24h"] == rainfall
