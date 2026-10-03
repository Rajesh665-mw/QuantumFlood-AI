"""
Unit Tests for Module 4 — Communication Failure & Network Resilience
"""
import pytest
from app.gis.geo_loader import get_risk_zone_geometry
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.services.network_resilience_service import simulate_network_failure


def test_network_failure_single_node_detection():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"
    candidates = generate_candidates()
    engine = ClassicalOptimizationEngine()
    sensors = engine.optimize(candidates, zones, 2.5, 8).selected_sensors
    conn = analyze_connectivity(sensors, 4.0, 4)

    assert len(conn.comm_nodes) > 0
    node_to_fail = conn.comm_nodes[0]["comm_node_id"]

    sim = simulate_network_failure(
        selected_sensors=sensors,
        comm_nodes=conn.comm_nodes,
        failed_node_ids=[node_to_fail],
        comm_range_km=4.0,
        zones=zones
    )

    assert sim["status"] == "SUCCESS"
    metrics = sim["metrics"]
    assert metrics["surviving_nodes_count"] == len(conn.comm_nodes) - 1
    assert metrics["post_failure_connectivity_pct"] <= metrics["baseline_connectivity_pct"]


def test_network_failure_recovery_recommendation():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"
    candidates = generate_candidates()
    engine = ClassicalOptimizationEngine()
    sensors = engine.optimize(candidates, zones, 2.5, 8).selected_sensors
    conn = analyze_connectivity(sensors, 4.0, 4)

    # Fail all comm nodes
    all_failed = [n["comm_node_id"] for n in conn.comm_nodes]

    sim = simulate_network_failure(
        selected_sensors=sensors,
        comm_nodes=conn.comm_nodes,
        failed_node_ids=all_failed,
        comm_range_km=4.0,
        zones=zones,
        candidate_pool=candidates
    )

    metrics = sim["metrics"]
    assert metrics["post_failure_connected"] == 0
    assert metrics["post_failure_disconnected"] == len(sensors)

    # Recovery plan should attempt to place a backup node
    plan = sim["recovery_plan"]
    assert plan is not None
    assert plan["action_type"] in ("DEPLOY_BACKUP_RELAY", "NO_VIABLE_RELAY_SITE")
    if plan["action_type"] == "DEPLOY_BACKUP_RELAY":
        assert plan["post_recovery_connectivity_pct"] > 0
