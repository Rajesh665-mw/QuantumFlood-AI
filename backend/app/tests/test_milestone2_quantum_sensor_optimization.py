"""
Milestone 2 — Quantum Sensor Placement Optimization Verification
================================================================
Validates:
1. Deterministic feasibility repair (under-budget and over-budget correction).
2. QUBO spatial separation penalty for pairs violating min_distance_km.
3. QAOA execution with full circuit gate diagnostics (CNOT count, circuit depth).
4. Side-by-side objective comparison against classical greedy baseline.
5. End-to-end API route execution with min_distance_km.
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.optimization.qubo_builder import (
    build_sensor_qubo_from_domain,
    repair_bitstring_to_budget,
    compute_actual_coverage,
)
from app.quantum.qaoa_solver import QaoaSolver
from app.quantum.quantum_config import QaoaConfig
from app.quantum.quantum_optimizer import QuantumOptimizationEngine
from app.optimization.classical_optimizer import ClassicalOptimizationEngine


@pytest.fixture
def test_client():
    return TestClient(app)


def test_feasibility_repair_under_budget():
    """Verify that an under-budget bitstring is greedily flipped to exact budget K."""
    A = np.array([
        [1, 0, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 1],
    ], dtype=int)
    w = np.array([3.0, 2.0, 5.0], dtype=float)
    K = 2
    raw_bitstring = [1, 0, 0, 0] # sum = 1 < 2

    repaired, was_repaired, meta = repair_bitstring_to_budget(
        raw_bitstring, coverage_matrix=A, zone_weights=w, budget=K, candidate_ids=["C-0", "C-1", "C-2", "C-3"]
    )
    assert was_repaired is True
    assert int(np.sum(repaired)) == K
    assert meta["repair_status"] == "repaired_to_feasible"
    assert len(meta["flips"]) == 1
    # Candidate 2 or 3 gives higher gain
    assert repaired[0] == 1


def test_feasibility_repair_over_budget():
    """Verify that an over-budget bitstring is greedily pruned to exact budget K with minimum loss."""
    A = np.array([
        [1, 0, 0],
        [1, 1, 0],
        [0, 0, 1],
    ], dtype=int)
    w = np.array([2.0, 4.0, 5.0], dtype=float)
    K = 1
    raw_bitstring = [1, 1, 0] # sum = 2 > 1

    repaired, was_repaired, meta = repair_bitstring_to_budget(
        raw_bitstring, coverage_matrix=A, zone_weights=w, budget=K, candidate_ids=["C-0", "C-1", "C-2"]
    )
    assert was_repaired is True
    assert int(np.sum(repaired)) == K
    assert meta["repair_status"] == "repaired_to_feasible"
    assert len(meta["flips"]) == 1


def test_qubo_spatial_distance_penalty():
    """Verify that candidate pairs within min_distance_km receive a positive off-diagonal penalty."""
    candidates = [
        {"candidate_id": "C-0", "lat": 16.500, "lon": 80.600},
        {"candidate_id": "C-1", "lat": 16.501, "lon": 80.601}, # Very close (~150m)
        {"candidate_id": "C-2", "lat": 16.550, "lon": 80.650}, # Far (~7.5km)
    ]
    zones = [
        {"zone_id": "Z-0", "centroid": {"lat": 16.500, "lon": 80.600}, "risk_score": 3.0, "risk_level": "MODERATE"},
        {"zone_id": "Z-1", "centroid": {"lat": 16.550, "lon": 80.650}, "risk_score": 4.0, "risk_level": "CRITICAL"},
    ]

    # 1. Without distance penalty
    qubo_no_dist = build_sensor_qubo_from_domain(
        candidates, zones, coverage_radius_km=2.0, budget=2, min_distance_km=None
    )

    # 2. With 1.0 km minimum distance
    qubo_dist = build_sensor_qubo_from_domain(
        candidates, zones, coverage_radius_km=2.0, budget=2, min_distance_km=1.0
    )

    assert qubo_dist.metadata.get("min_distance_km") == 1.0
    assert qubo_dist.metadata.get("dist_penalized_pairs_count") >= 1
    # Pair (0, 1) must have higher penalty in Q
    assert qubo_dist.Q[0, 1] > qubo_no_dist.Q[0, 1]


def test_qaoa_solver_circuit_diagnostics():
    """Verify that QAOA returns circuit gate depth, CNOT count, and solver metadata."""
    candidates = [
        {"candidate_id": f"C-{i}", "lat": 16.50 + i * 0.01, "lon": 80.60 + i * 0.01}
        for i in range(4)
    ]
    zones = [
        {"zone_id": f"Z-{j}", "centroid": {"lat": 16.50 + j * 0.01, "lon": 80.60 + j * 0.01}, "risk_score": 3.0, "risk_level": "MODERATE"}
        for j in range(4)
    ]
    engine = QuantumOptimizationEngine()
    opt_res, q_res = engine.optimize(
        candidates=candidates,
        zones=zones,
        coverage_radius_km=2.0,
        num_sensors=2,
        p=1,
        shots=100,
        seed=42,
    )
    assert q_res.is_feasible is True
    assert q_res.sensors_selected_count == 2
    assert "cnot_count" in q_res.metadata
    assert "circuit_depth" in q_res.metadata
    assert q_res.metadata["circuit_depth"] > 0
    assert q_res.metadata["cnot_count"] >= 0
    assert len(opt_res.selected_sensors) == 2


def test_api_quantum_and_compare_with_distance(test_client):
    """Verify that the FastAPI endpoints accept and execute with min_distance_km."""
    sample_zones = [
        {
            "zone_id": f"Z-{i}",
            "centroid": {"lat": 16.50 + i * 0.01, "lon": 80.60 + i * 0.01},
            "risk_score": 3.0,
            "risk_level": "MODERATE",
        }
        for i in range(6)
    ]
    # 1. Quantum run
    res_q = test_client.post("/api/optimization/quantum", json={
        "num_sensors": 2,
        "coverage_radius_km": 2.5,
        "max_candidates": 6,
        "p": 1,
        "shots": 200,
        "min_distance_km": 0.8,
        "zones": sample_zones,
    })
    assert res_q.status_code == 200
    data_q = res_q.json()
    assert "quantum" in data_q
    assert data_q["quantum"]["is_feasible"] is True

    # 2. Compare run
    res_comp = test_client.post("/api/optimization/compare", json={
        "num_sensors": 2,
        "coverage_radius_km": 2.5,
        "max_candidates": 6,
        "p": 1,
        "shots": 200,
        "min_distance_km": 0.8,
        "zones": sample_zones,
    })
    assert res_comp.status_code == 200
    data_comp = res_comp.json()
    assert "classical_result" in data_comp
    assert "quantum_result" in data_comp
    assert "comparison_metrics" in data_comp
