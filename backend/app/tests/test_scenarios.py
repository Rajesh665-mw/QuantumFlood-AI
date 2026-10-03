"""
Unit Tests for Module 6 — Multi-Scenario Flood Simulation & Comparison
"""
import pytest
from app.services.scenario_service import (
    SCENARIO_PRESETS,
    run_scenario_pipeline,
    compare_scenarios,
    activate_scenario_in_pipeline
)
from app.services.pipeline_state import state


def test_scenario_presets_exist():
    assert len(SCENARIO_PRESETS) >= 3
    ids = [p["id"] for p in SCENARIO_PRESETS]
    assert "baseline" in ids
    assert "moderate" in ids
    assert "severe" in ids


def test_run_scenario_pipeline_full_propagation():
    run = run_scenario_pipeline(
        scenario_id="test_severe",
        name="Test Severe Scenario",
        water_level_m=14.5,
        inflow_ktcmd=1100.0,
        rainfall_mm_24h=140.0,
        resolution="low"
    )

    assert run["scenario_id"] == "test_severe"
    metrics = run["metrics"]
    assert metrics["critical_zones_count"] > 0
    assert metrics["sensor_coverage_percentage"] > 0
    assert metrics["connected_sensors_count"] > 0
    assert "pipeline_artifacts" in run
    assert "risk_map" in run["pipeline_artifacts"]
    assert "safe_locations" in run["pipeline_artifacts"]


def test_compare_scenarios_produces_matrix():
    comp = compare_scenarios()
    assert comp["total_scenarios"] >= 3
    assert len(comp["comparison_table"]) >= 5
    assert len(comp["scenarios"]) >= 3


def test_activate_scenario_updates_pipeline_state():
    act = activate_scenario_in_pipeline("moderate")
    assert act["status"] == "ACTIVATED"
    assert state.latest_risk_map is not None
    assert state.latest_optimization is not None
    assert state.latest_connectivity is not None
    assert state.latest_recommendations is not None
