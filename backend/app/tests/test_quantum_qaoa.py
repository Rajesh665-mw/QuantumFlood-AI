"""
Test Suite for Quantum QAOA & Comparison Layer
==============================================
Validates:
  1. Exact Union Coverage and Multi-Sensor Overlap Dynamics (1, 2, 3+ sensors, duplicates).
  2. QAOA Statevector Evolution, Unitary Normalization, and Optimization.
  3. Benchmark Instance Ground Truth (N=5, M=6, K=2 -> Coverage = 35.0, (C0, C3)/(C0, C4)).
  4. Progressive Benchmarks & Deterministic Randomized Validation.
  5. OptimizationComparisonEngine Metrics & Academic Honesty.
  6. FastAPI Route Integration (/api/optimization/quantum and /api/optimization/compare).
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.quantum.quantum_config import QaoaConfig
from app.quantum.qaoa_solver import QaoaSolver
from app.quantum.quantum_result import QuantumOptimizationResult
from app.optimization.qubo_builder import (
    build_sensor_qubo,
    build_exact_sensor_qubo,
    evaluate_qubo,
    compute_actual_coverage,
    verify_coverage_exactness,
)
from app.optimization.comparison_engine import OptimizationComparisonEngine
from app.services.pipeline_state import state

# Benchmark fixtures from QUANTUM_FORMULATION_REPORT.md
BENCHMARK_COVERAGE_MATRIX = np.array([
    [1, 1, 0, 0, 0],
    [1, 0, 1, 0, 0],
    [0, 1, 1, 1, 0],
    [0, 0, 0, 1, 1],
    [0, 0, 0, 1, 1],
    [0, 0, 1, 0, 1],
], dtype=int)
BENCHMARK_ZONE_WEIGHTS = np.array([10.0, 7.5, 5.0, 2.5, 10.0, 5.0], dtype=float)
BENCHMARK_CANDIDATE_IDS = ["C0", "C1", "C2", "C3", "C4"]


# ============================================================================
# 1. Exact Union Coverage & Multi-Sensor Overlap Tests
# ============================================================================
class TestUnionCoverageAndOverlaps:
    """Verifies that zone coverage is a true set-union operation."""

    def test_single_sensor_covering_zone(self):
        """Zone covered by exactly 1 selected sensor: w_z counted once."""
        A = np.array([[1, 0]])
        w = np.array([10.0])
        res = build_sensor_qubo(A, w, budget=1, penalty=20.0)
        cov = compute_actual_coverage([1, 0], A, w)
        assert cov == 10.0
        # Check QUBO energy
        E = evaluate_qubo([1, 0], res.Q, res.offset)
        assert abs(E - (-10.0)) < 1e-6

    def test_two_sensors_covering_same_zone(self):
        """Zone covered by 2 selected sensors: pairwise overlap cancels duplicate weight."""
        A = np.array([[1, 1]])
        w = np.array([10.0])
        res = build_sensor_qubo(A, w, budget=2, penalty=25.0)
        cov = compute_actual_coverage([1, 1], A, w)
        assert cov == 10.0
        E = evaluate_qubo([1, 1], res.Q, res.offset)
        # alpha_0 = 10, alpha_1 = 10, beta_01 = 10. Coverage = 10 + 10 - 10 = 10.
        # Energy = -10 + 25*(2-2)^2 = -10.0
        assert abs(E - (-10.0)) < 1e-6

    def test_three_sensors_covering_same_zone_pairwise_vs_exact(self):
        """
        Demonstrates the exactness behavior when 3 sensors cover the same zone:
        - Pairwise formulation incurs truncation (3 - 3 = 0).
        - Exact auxiliary formulation restores true coverage (10.0).
        """
        A = np.array([[1, 1, 1]])
        w = np.array([10.0])
        
        # 1. Direct true coverage
        assert compute_actual_coverage([1, 1, 1], A, w) == 10.0

        # 2. Pairwise audit verifies truncation
        audit_pairwise = verify_coverage_exactness(A, w, budget=3, mode="pairwise")
        assert not audit_pairwise["is_strictly_exact"]
        assert audit_pairwise["discrepant_states_count"] == 1
        assert audit_pairwise["max_discrepancy"] == 10.0

        # 3. Exact auxiliary formulation audits as 100% exact
        audit_exact = verify_coverage_exactness(A, w, budget=3, mode="exact")
        assert audit_exact["is_strictly_exact"]
        assert audit_exact["max_discrepancy"] == 0.0

    def test_duplicate_candidates_handled_correctly(self):
        """Two identical candidate sensors: union coverage does not double-count."""
        A = np.array([
            [1, 1],
            [1, 1],
        ])
        w = np.array([5.0, 5.0])
        res = build_sensor_qubo(A, w, budget=2, penalty=20.0)
        cov = compute_actual_coverage([1, 1], A, w)
        assert cov == 10.0
        E = evaluate_qubo([1, 1], res.Q, res.offset)
        assert abs(E - (-10.0)) < 1e-6

    def test_benchmark_is_provably_exact_for_k_equals_two(self):
        """For the benchmark with K=2, 3-way overlap is impossible; pairwise is 100% exact."""
        audit = verify_coverage_exactness(
            BENCHMARK_COVERAGE_MATRIX,
            BENCHMARK_ZONE_WEIGHTS,
            budget=2,
            mode="pairwise",
        )
        assert audit["is_strictly_exact"]
        assert audit["max_discrepancy"] == 0.0


# ============================================================================
# 2. QAOA Solver Core Unit Tests
# ============================================================================
class TestQaoaSolverInternals:
    """Verifies quantum statevector evolution, normalization, and optimization."""

    def test_statevector_normalization_maintained(self):
        """Statevector |psi> must satisfy sum |psi_i|^2 = 1.0 at every step."""
        solver = QaoaSolver(QaoaConfig(p=2, shots=100))
        qubo = build_sensor_qubo(BENCHMARK_COVERAGE_MATRIX, BENCHMARK_ZONE_WEIGHTS, budget=2)
        basis, energies = solver._precompute_basis_and_energies(qubo.Q, qubo.offset)
        
        # Test random angles
        angles = np.array([0.3, 0.6, 0.4, 0.8])
        exp_val, probs = solver._simulate_circuit(angles, p=2, energies=energies, dim=32, N=5)
        
        assert abs(np.sum(probs) - 1.0) < 1e-9
        assert np.all(probs >= 0.0)

    def test_qaoa_p1_and_p2_execution(self):
        """QAOA solves successfully at both depth p=1 and p=2."""
        for p in (1, 2):
            solver = QaoaSolver(QaoaConfig(p=p, shots=512, seed=42, max_iter=40))
            result = solver.optimize(
                BENCHMARK_COVERAGE_MATRIX,
                BENCHMARK_ZONE_WEIGHTS,
                budget=2,
                candidate_ids=BENCHMARK_CANDIDATE_IDS,
            )
            assert isinstance(result, QuantumOptimizationResult)
            assert result.is_feasible
            assert result.sensors_selected_count == 2
            assert result.qaoa_depth_p == p
            assert len(result.optimal_gamma) == p
            assert len(result.optimal_beta) == p
            assert result.weighted_coverage > 0.0


# ============================================================================
# 3. Benchmark Ground Truth Validation (N=5, M=6, K=2)
# ============================================================================
class TestBenchmarkValidation:
    """Validates QAOA against the benchmark from QUANTUM_FORMULATION_REPORT.md."""

    def test_qaoa_discovers_global_optimum_35(self):
        """QAOA finds optimal coverage 35.0 and selects (C0, C3) or (C0, C4)."""
        solver = QaoaSolver(QaoaConfig(p=2, shots=1024, seed=42, max_iter=80))
        result = solver.optimize(
            BENCHMARK_COVERAGE_MATRIX,
            BENCHMARK_ZONE_WEIGHTS,
            budget=2,
            candidate_ids=BENCHMARK_CANDIDATE_IDS,
        )

        assert result.is_feasible, f"Result not feasible: {result.selected_candidate_ids}"
        assert result.weighted_coverage == 35.0, f"Expected 35.0, got {result.weighted_coverage}"
        
        selected_set = set(result.selected_candidate_ids)
        assert selected_set in ({"C0", "C3"}, {"C0", "C4"}), f"Unexpected selection: {selected_set}"
        assert result.qubo_energy == -35.0
        assert result.solution_probability > 0.05

    def test_qaoa_with_exact_auxiliary_formulation(self):
        """QAOA solves cleanly using the exact auxiliary variable QUBO."""
        solver = QaoaSolver(QaoaConfig(p=1, shots=1024, seed=42, formulation_mode="exact"))
        result = solver.optimize(
            BENCHMARK_COVERAGE_MATRIX,
            BENCHMARK_ZONE_WEIGHTS,
            budget=2,
            candidate_ids=BENCHMARK_CANDIDATE_IDS,
        )
        assert result.is_feasible
        assert result.weighted_coverage == 35.0


# ============================================================================
# 4. Progressive Benchmarks & Randomized Validation
# ============================================================================
class TestProgressiveAndRandomizedBenchmarks:
    """Tests progressive sizes and randomized problem instances."""

    @pytest.mark.parametrize("seed,N,M,K", [
        (42, 5, 6, 2),
        (101, 6, 6, 2),
        (202, 6, 7, 2),
    ])
    def test_randomized_qaoa_matches_or_approximates_optimum(self, seed, N, M, K):
        """On small instances, QAOA achieves high approximation ratio against exhaustive optimum."""
        rng = np.random.RandomState(seed)
        A = rng.binomial(1, 0.45, size=(M, N))
        # Ensure every zone is covered by at least one candidate
        for z in range(M):
            if np.sum(A[z]) == 0:
                A[z, rng.randint(0, N)] = 1
        w = rng.uniform(2.0, 15.0, size=M).round(1)

        # 1. Exhaustive optimum
        import itertools
        best_cov = -1.0
        for indices in itertools.combinations(range(N), K):
            x = np.zeros(N, dtype=int)
            for idx in indices:
                x[idx] = 1
            cov = compute_actual_coverage(x, A, w)
            if cov > best_cov:
                best_cov = cov

        # 2. QAOA
        solver = QaoaSolver(QaoaConfig(p=2, shots=1024, seed=seed, max_iter=60))
        res = solver.optimize(A, w, budget=K)

        assert res.is_feasible
        approx_ratio = res.weighted_coverage / best_cov
        assert approx_ratio >= 0.85, f"Approximation ratio {approx_ratio:.3f} below 0.85 on seed {seed}"


# ============================================================================
# 5. Optimization Comparison Engine Tests
# ============================================================================
class TestComparisonEngine:
    """Verifies that OptimizationComparisonEngine produces unbiased comparisons."""

    def test_compare_on_mock_domain_data(self):
        candidates = [
            {"candidate_id": f"C-{i}", "lat": 16.51 + i * 0.01, "lon": 80.62 + i * 0.01}
            for i in range(5)
        ]
        zones = [
            {"zone_id": f"Z-{z}", "centroid": {"lat": 16.51 + z * 0.01, "lon": 80.62 + z * 0.01}, "risk_score": 10.0, "risk_level": "MODERATE"}
            for z in range(6)
        ]

        engine = OptimizationComparisonEngine()
        report = engine.compare(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=3.0,
            num_sensors=2,
            p=1,
            shots=512,
            seed=42,
        )

        assert "classical_result" in report
        assert "quantum_result" in report
        assert "exhaustive_ground_truth" in report
        assert "academic_assessment" in report
        assert report["quantum_result"]["is_feasible"]
        assert report["comparison_metrics"]["quantum_to_classical_ratio"] > 0.0


# ============================================================================
# 6. FastAPI Route Integration Tests
# ============================================================================
class TestFastApiQuantumRoutes:
    """Tests the new backend endpoints: /api/optimization/quantum & /api/optimization/compare."""

    @pytest.fixture(autouse=True)
    def setup_risk_state(self):
        """Ensure state.latest_risk_map is populated."""
        state.latest_risk_map = {
            "resolution": "default",
            "zones": [
                {
                    "zone_id": f"Z{i:02d}",
                    "name": f"Zone {i}",
                    "centroid": {"lat": 16.50 + i * 0.01, "lon": 80.60 + i * 0.01},
                    "risk_score": 10.0,
                    "risk_level": "HIGH",
                }
                for i in range(6)
            ],
        }

    def test_post_quantum_optimization_endpoint(self):
        client = TestClient(app)
        payload = {
            "num_sensors": 2,
            "coverage_radius_km": 3.5,
            "p": 1,
            "shots": 512,
            "seed": 42,
        }
        res = client.post("/api/optimization/quantum", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "optimization" in data
        assert "quantum" in data
        assert data["quantum"]["is_feasible"]
        assert data["quantum"]["sensor_budget"] == 2

    def test_post_compare_solvers_endpoint(self):
        client = TestClient(app)
        payload = {
            "num_sensors": 2,
            "coverage_radius_km": 3.5,
            "p": 1,
            "shots": 512,
            "seed": 42,
        }
        res = client.post("/api/optimization/compare", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert "classical_result" in data
        assert "quantum_result" in data
        assert "academic_assessment" in data
