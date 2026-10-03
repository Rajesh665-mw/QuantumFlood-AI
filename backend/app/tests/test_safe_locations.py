"""
Unit Tests for Module 1 — Risk-Aware Safe Location Finder
"""
import pytest
from app.gis.geo_loader import get_risk_zone_geometry
from app.risk.risk_engine import generate_zone_risk_map
from app.services.safe_location_service import evaluate_safe_locations, load_candidate_safe_locations


def test_candidate_facilities_loaded_and_have_provenance():
    candidates = load_candidate_safe_locations()
    assert len(candidates) >= 10
    for feat in candidates:
        props = feat["properties"]
        assert "id" in props
        assert "name" in props
        assert "elevation_m" in props
        assert props["elevation_m"] > 0
        assert props["capacity_surveyed"] is False
        assert props["capacity_status"] == "UNAVAILABLE"
        coords = feat["geometry"]["coordinates"]
        assert len(coords) == 2
        # Check coordinates within or immediately bounding study corridor
        assert 80.50 <= coords[0] <= 80.75
        assert 16.40 <= coords[1] <= 16.60


def test_safe_locations_scoring_determinism():
    zones = get_risk_zone_geometry("default")
    # Mark first few zones as CRITICAL and others as LOW
    for i, z in enumerate(zones):
        z["risk_score"] = 4 if i < 6 else 1
        z["risk_level"] = "CRITICAL" if i < 6 else "LOW"

    run1 = evaluate_safe_locations(zones, 0.25, 0.35, 0.20, 0.20)
    run2 = evaluate_safe_locations(zones, 0.25, 0.35, 0.20, 0.20)

    assert run1["total_candidates"] == run2["total_candidates"]
    assert len(run1["locations"]) == len(run2["locations"])
    for loc1, loc2 in zip(run1["locations"], run2["locations"]):
        assert loc1["id"] == loc2["id"]
        assert loc1["recommendation_score"] == loc2["recommendation_score"]
        assert "Recommended" in loc1["explanation"]


def test_safe_locations_weight_variation_influences_ranking():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 2
        z["risk_level"] = "MODERATE"

    # Heavily weight elevation
    elev_heavy = evaluate_safe_locations(zones, weight_elevation=0.9, weight_risk=0.03, weight_distance=0.03, weight_accessibility=0.04)
    # Heavily weight accessibility
    access_heavy = evaluate_safe_locations(zones, weight_elevation=0.03, weight_risk=0.03, weight_distance=0.04, weight_accessibility=0.9)

    top_elev = elev_heavy["locations"][0]
    top_access = access_heavy["locations"][0]

    assert top_elev["elevation_m"] >= 26.0
    assert top_access["accessibility_score"] >= 0.8


def test_safe_locations_filters():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"

    filtered = evaluate_safe_locations(zones, min_elevation_m=26.0)
    for loc in filtered["locations"]:
        assert loc["elevation_m"] >= 26.0
