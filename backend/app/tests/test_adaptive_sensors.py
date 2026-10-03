"""
Unit Tests for Module 3 — Adaptive Sensor Redeployment
"""
import pytest
from app.gis.geo_loader import get_risk_zone_geometry
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.services.adaptive_sensor_service import solve_adaptive_redeployment


def test_adaptive_sensor_redeployment_actions_and_metrics():
    zones = get_risk_zone_geometry("default")

    # Baseline condition: uniform low risk
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"

    candidates = generate_candidates()
    engine = ClassicalOptimizationEngine()
    baseline_opt = engine.optimize(candidates, zones, 2.5, 6)
    initial_sensors = baseline_opt.selected_sensors

    # Updated condition: river zones surge to CRITICAL
    updated_zones = get_risk_zone_geometry("default")
    for z in updated_zones:
        if z["distance_to_river_km"] < 2.0:
            z["risk_score"] = 4
            z["risk_level"] = "CRITICAL"
        else:
            z["risk_score"] = 1
            z["risk_level"] = "LOW"

    result = solve_adaptive_redeployment(
        current_sensors=initial_sensors,
        updated_zones=updated_zones,
        sensor_budget=6,
        coverage_radius_km=2.5
    )

    assert result["status"] == "SUCCESS"
    assert len(result["actions"]) == 6

    actions = result["actions"]
    action_types = {a["action"] for a in actions}
    # At least KEEP or RELOCATE should be present
    assert "KEEP" in action_types or "RELOCATE" in action_types

    summary = result["summary"]
    assert summary["total_sensors_deployed"] == 6
    assert summary["updated_coverage"]["weighted_risk_coverage"] >= summary["baseline_coverage"]["weighted_risk_coverage"]
    assert "recommendation_narrative" in result


def test_adaptive_sensor_redeployment_with_budget_increase():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"
    candidates = generate_candidates()
    engine = ClassicalOptimizationEngine()
    initial_sensors = engine.optimize(candidates, zones, 2.5, 4).selected_sensors

    # Increased budget to 6
    result = solve_adaptive_redeployment(
        current_sensors=initial_sensors,
        updated_zones=zones,
        sensor_budget=6,
        coverage_radius_km=2.5
    )

    summary = result["summary"]
    assert summary["total_sensors_deployed"] == 6
    # Should contain ADD actions
    add_actions = [a for a in result["actions"] if a["action"] == "ADD"]
    assert len(add_actions) == 2


def test_adaptive_sensor_redeployment_handles_zones_without_risk_score_gracefully():
    """Regression test: solve_adaptive_redeployment should not crash with KeyError if zones lack risk_score."""
    raw_zones = get_risk_zone_geometry("default")  # Raw geometry without risk_score key
    candidates = generate_candidates()
    result = solve_adaptive_redeployment(
        current_sensors=candidates[:4],
        updated_zones=raw_zones,
        sensor_budget=4,
        coverage_radius_km=2.5
    )
    assert result["status"] == "SUCCESS"
    assert len(result["actions"]) == 4
