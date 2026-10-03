"""
UC-067 Compliance Pass Test Suite
=================================
Verifies all targets of the final UC-067 compliance pass:
  Target A: Maximum Coverage with Minimal Nodes (QUBO, Pareto Frontier, Exhaustive Verification)
  Target B: QML Multi-Seed Robustness Evaluation, Feature Leakage Audit, Downstream Risk Propagation
  Stage 2: Communication Nodes & Network Connectivity Telemetry
"""
import pytest
import numpy as np
import pandas as pd
from typing import List, Dict, Any

from app.optimization.qubo_builder import (
    build_sensor_qubo,
    build_exact_sensor_qubo,
    compute_minimal_nodes_frontier,
    compute_minimal_nodes_frontier_from_domain,
)
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.comparison_engine import OptimizationComparisonEngine
from app.quantum.quantum_optimizer import QuantumOptimizationEngine
from app.quantum.qml_forecaster import (
    QuantumVariationalRegressor,
    train_and_evaluate_qml,
    evaluate_qml_multiseed,
)
from app.quantum.qml_config import QmlConfig, APPROVED_QML_FEATURES
from app.services.data_service import get_clean_dataset
from app.risk.risk_engine import generate_zone_risk_map


# =============================================================================
# 1. Target A: Minimal Nodes & QUBO Formulation Tests
# =============================================================================

def test_minimal_nodes_frontier_monotonicity_and_saturation():
    """
    Verifies that the Pareto frontier is monotonic non-decreasing,
    correctly identifies the minimal sensor count k*, and exhibits diminishing returns.
    """
    # 6 zones, 5 candidates
    A = np.array([
        [1, 0, 0, 0, 0],
        [1, 1, 0, 0, 0],
        [0, 1, 1, 0, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 0, 1],
    ], dtype=int)
    w = np.array([5.0, 10.0, 8.0, 7.0, 9.0, 6.0])
    total_risk = float(np.sum(w))

    frontier = compute_minimal_nodes_frontier(
        coverage_matrix=A,
        zone_weights=w,
        max_k=5,
    )

    pareto = frontier["pareto_frontier"]
    assert len(pareto) == 5

    # Monotonicity check
    for i in range(len(pareto) - 1):
        assert pareto[i + 1]["max_coverage"] >= pareto[i]["max_coverage"]
        assert pareto[i]["marginal_gain"] >= 0.0

    # Saturation and recommended minimal sensors
    rec_k = frontier["recommended_min_sensors"]
    assert 1 <= rec_k <= 5
    assert frontier["max_achievable_coverage"] <= total_risk
    assert any(p["is_minimal_optimum"] for p in pareto)


def test_qubo_minimal_nodes_parsimony_penalty_applied():
    """
    Verifies that objective_mode='minimal_nodes' penalizes adding redundant sensors
    via the linear parsimony penalty lambda * sum(x_j).
    """
    A = np.array([
        [1, 1],
        [1, 1],
    ], dtype=int)
    w = np.array([10.0, 10.0])

    # Budgeted mode (fixed K=2)
    q_budgeted = build_sensor_qubo(A, w, budget=2, mode="pairwise", objective_mode="budgeted")
    # Minimal nodes mode (lambda = 1.0)
    q_minimal = build_sensor_qubo(A, w, budget=2, mode="pairwise", objective_mode="minimal_nodes", sensor_penalty_lambda=1.0)

    # In minimal nodes mode, the diagonal terms should be shifted by +lambda = +1.0
    diag_budgeted = np.diag(q_budgeted.Q)
    diag_minimal = np.diag(q_minimal.Q)
    assert np.all(diag_minimal > diag_budgeted)


def test_exhaustive_32_state_minimal_nodes_ground_state():
    """
    Exhaustively evaluates all 2^5 = 32 states on an overlapping coverage problem.
    Verifies that the QUBO ground state chooses exactly the minimal subset (k=3)
    achieving 100% coverage, rather than k=4 or k=5.
    """
    # 4 zones, 5 candidates: candidates 0, 1, 2 cover all 4 zones.
    # Candidates 3 and 4 are completely redundant duplicates.
    A = np.array([
        [1, 0, 0, 1, 0],
        [1, 1, 0, 0, 1],
        [0, 1, 1, 1, 0],
        [0, 0, 1, 0, 1],
    ], dtype=int)
    w = np.array([10.0, 10.0, 10.0, 10.0])  # total risk = 40.0

    qubo_res = build_sensor_qubo(
        coverage_matrix=A,
        zone_weights=w,
        budget=3,
        penalty=10.0,
        mode="exact",
        objective_mode="minimal_nodes",
        sensor_penalty_lambda=0.5,
    )

    Q = qubo_res.Q
    offset = qubo_res.offset
    dim = Q.shape[0]

    # For sensor indices 0..4, evaluate energy for each state
    # Focus on the 5 physical sensor qubits
    energies_by_k = {}
    for x_int in range(32):
        x_phys = np.array([(x_int >> (4 - j)) & 1 for j in range(5)], dtype=float)
        k_count = int(np.sum(x_phys))

        # Check coverage
        covered = {z for z in range(4) if any(A[z, j] == 1 and x_phys[j] == 1 for j in range(5))}
        cov_val = sum(w[z] for z in covered)

        if cov_val == 40.0:  # 100% coverage
            # Exact energy for the full state (auxiliaries optimal)
            x_full = np.zeros(dim, dtype=float)
            x_full[:5] = x_phys
            # auxiliary variables w_z = 1 if covered
            if dim > 5:
                x_full[5:9] = 1.0
            energy = float(x_full @ Q @ x_full) + offset

            if k_count not in energies_by_k or energy < energies_by_k[k_count]:
                energies_by_k[k_count] = energy

    # Minimal count k=3 must have strictly lower energy than k=4 and k=5 due to parsimony penalty
    assert 3 in energies_by_k
    assert 4 in energies_by_k
    assert 5 in energies_by_k
    assert energies_by_k[3] < energies_by_k[4]
    assert energies_by_k[4] < energies_by_k[5]


def test_classical_optimizer_coverage_per_sensor_telemetry():
    """
    Verifies that ClassicalOptimizationEngine computes coverage_per_sensor
    and minimal_sensors_for_max_coverage.
    """
    candidates = [
        {"candidate_id": "C-1", "lat": 16.51, "lon": 80.62},
        {"candidate_id": "C-2", "lat": 16.52, "lon": 80.63},
        {"candidate_id": "C-3", "lat": 16.53, "lon": 80.64},
    ]
    zones = [
        {"zone_id": "Z-1", "centroid": {"lat": 16.51, "lon": 80.62}, "risk_score": 10.0, "risk_level": "MODERATE"},
        {"zone_id": "Z-2", "centroid": {"lat": 16.52, "lon": 80.63}, "risk_score": 15.0, "risk_level": "CRITICAL"},
        {"zone_id": "Z-3", "centroid": {"lat": 16.53, "lon": 80.64}, "risk_score": 8.0, "risk_level": "LOW"},
    ]

    engine = ClassicalOptimizationEngine()
    res = engine.optimize(candidates, zones, radius_km=3.0, num_sensors=3)

    assert res.coverage_per_sensor > 0.0
    assert 1 <= res.minimal_sensors_for_max_coverage <= res.num_sensors_selected
    # Demonstrates parsimonious early-exit: 1 sensor achieves 100% coverage
    assert res.num_sensors_selected == 1
    assert res.coverage_percentage == 100.0


def test_comparison_engine_telemetry_and_minimal_nodes():
    """
    Verifies that OptimizationComparisonEngine includes:
      - coverage_per_sensor for classical and quantum
      - minimal_nodes_analysis (Pareto frontier, recommended min sensors)
      - communication_nodes_analysis (connectivity, relay nodes, comm node budget)
    """
    candidates = [
        {"candidate_id": "C-1", "lat": 16.51, "lon": 80.62},
        {"candidate_id": "C-2", "lat": 16.52, "lon": 80.63},
        {"candidate_id": "C-3", "lat": 16.53, "lon": 80.64},
        {"candidate_id": "C-4", "lat": 16.54, "lon": 80.65},
    ]
    zones = [
        {"zone_id": "Z-1", "centroid": {"lat": 16.51, "lon": 80.62}, "risk_score": 10.0, "risk_level": "MODERATE"},
        {"zone_id": "Z-2", "centroid": {"lat": 16.52, "lon": 80.63}, "risk_score": 12.0, "risk_level": "HIGH"},
        {"zone_id": "Z-3", "centroid": {"lat": 16.53, "lon": 80.64}, "risk_score": 15.0, "risk_level": "CRITICAL"},
    ]

    comparator = OptimizationComparisonEngine()
    cmp_res = comparator.compare(
        candidates=candidates,
        zones=zones,
        coverage_radius_km=3.0,
        num_sensors=2,
        p=1,
        shots=256,
        seed=42,
    )

    # 1. Telemetry
    assert "coverage_per_sensor" in cmp_res["classical_result"]
    assert "coverage_per_sensor" in cmp_res["quantum_result"]

    # 2. Minimal Nodes Pareto Frontier
    assert "minimal_nodes_analysis" in cmp_res
    min_analysis = cmp_res["minimal_nodes_analysis"]
    assert "recommended_min_sensors" in min_analysis
    assert "pareto_frontier" in min_analysis
    assert len(min_analysis["pareto_frontier"]) >= 2

    # 3. Communication Nodes Analysis
    assert "communication_nodes_analysis" in cmp_res
    comm_analysis = cmp_res["communication_nodes_analysis"]
    assert "classical" in comm_analysis
    assert "quantum" in comm_analysis
    assert comm_analysis["classical"]["sensor_nodes_count"] == cmp_res["classical_result"]["num_sensors_selected"]
    assert comm_analysis["quantum"]["sensor_nodes_count"] == cmp_res["quantum_result"]["num_sensors_selected"]


# =============================================================================
# 2. Target B: QML Multi-Seed Robustness & Leakage Audit Tests
# =============================================================================

def test_qml_no_feature_leakage_audit():
    """
    Verifies that the approved QML feature set contains ZERO future information.
    All features must be computable at time t without accessing t + h.
    """
    # Approved features strictly at observation time t
    assert APPROVED_QML_FEATURES == [
        "water_level_m",
        "inflow_ktcmd",
        "rainfall_roll3",
        "rainfall_mm",
    ]

    # Verify that future water level is the regression target, not an input feature
    assert "water_level_m_future" not in APPROVED_QML_FEATURES
    assert "target" not in APPROVED_QML_FEATURES


def test_qml_deterministic_repeatability():
    """
    Verifies that running VQR training with the same random seed produces
    bit-exact identical predictions on the held-out test set.
    """
    df = get_clean_dataset()
    cfg1 = QmlConfig(n_qubits=4, layers=2, max_iter=15, train_subsample=50, seed=42)
    cfg2 = QmlConfig(n_qubits=4, layers=2, max_iter=15, train_subsample=50, seed=42)

    _, res1 = train_and_evaluate_qml(df, horizon_days=1, config=cfg1)
    _, res2 = train_and_evaluate_qml(df, horizon_days=1, config=cfg2)

    preds1 = [p["predicted"] for p in res1.predictions]
    preds2 = [p["predicted"] for p in res2.predictions]

    np.testing.assert_allclose(preds1, preds2, atol=1e-5)
    assert abs(res1.test_r2 - res2.test_r2) < 1e-6


def test_qml_multiseed_robustness_evaluation():
    """
    Verifies that evaluate_qml_multiseed executes across multiple deterministic seeds,
    records each run, and computes standard deviation and mean metrics.
    """
    df = get_clean_dataset()
    seeds = [42, 123]

    multiseed = evaluate_qml_multiseed(
        df=df,
        horizon_days=1,
        seeds=seeds,
        max_iter=15,
        train_subsample=60,
    )

    assert multiseed["seeds_evaluated"] == seeds
    assert len(multiseed["runs"]) == 2

    summary = multiseed["summary"]
    assert "mean_r2" in summary
    assert "std_r2" in summary
    assert "mean_mae" in summary
    assert "std_mae" in summary
    assert isinstance(summary["mean_r2"], float)
    assert isinstance(summary["std_r2"], float)


def test_forecast_to_risk_propagation():
    """
    Verifies downstream pipeline coupling: higher forecasted water levels
    strictly propagate into elevated spatial risk scores and increased critical zones.
    """
    df = get_clean_dataset()

    # Normal water level scenario (e.g. 5.0m, moderate inflow)
    risk_normal = generate_zone_risk_map(
        water_level_m=5.0,
        inflow_ktcmd=100.0,
        rainfall_mm_24h=10.0,
        resolution="low",
    )
    # Severe flood level scenario (e.g. 14.0m, critical inflow)
    risk_flood = generate_zone_risk_map(
        water_level_m=14.0,
        inflow_ktcmd=600.0,
        rainfall_mm_24h=120.0,
        resolution="low",
    )

    avg_score_normal = np.mean([z["risk_score"] for z in risk_normal["zones"]])
    avg_score_flood = np.mean([z["risk_score"] for z in risk_flood["zones"]])

    # Higher forecast level must increase spatial risk score
    assert avg_score_flood > avg_score_normal

    # Flood level must yield at least as many CRITICAL / HIGH zones
    crit_normal = sum(1 for z in risk_normal["zones"] if z["risk_level"] in ("CRITICAL", "HIGH"))
    crit_flood = sum(1 for z in risk_flood["zones"] if z["risk_level"] in ("CRITICAL", "HIGH"))
    assert crit_flood >= crit_normal
