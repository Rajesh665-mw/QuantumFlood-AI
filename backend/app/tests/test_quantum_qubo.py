"""
Unit & Algorithmic Validation Tests for QUBO Formulation Layer
==============================================================
Validates the QUBO formulation of the Weighted Maximum Coverage Problem for
flood sensor placement without depending on quantum hardware or Qiskit.

Tests:
1. Exact Benchmark Instance (5 candidates, 6 zones, K=2) from QUANTUM_FORMULATION_REPORT.md
2. Exhaustive 32-state enumeration vs ground-truth combinatorial search
3. Non-circular independent direct coverage validation
4. Multi-instance randomized testing across diverse (N, M, K) configurations
5. Penalty parameter sensitivity analysis (P > max(alpha) guarantee and failure when P is small)
6. Comprehensive edge cases (K=N, K<1, K>N, empty, single-element, zero/negative weights)
7. Domain adapter integration with QuantumFlood candidate and zone geometries
"""
import itertools
import pytest
import numpy as np

from app.optimization.qubo_builder import (
    build_sensor_qubo,
    build_sensor_qubo_from_domain,
    evaluate_qubo,
    decode_solution,
    compute_actual_coverage,
    recommend_penalty,
    validate_binary_vector,
    QuboResult,
)


# ---------------------------------------------------------------------------
# Standard Benchmark Fixture (from QUANTUM_FORMULATION_REPORT.md)
# ---------------------------------------------------------------------------
@pytest.fixture
def benchmark_data():
    weights = np.array([10.0, 7.5, 5.0, 2.5, 10.0, 5.0])
    A = np.array([
        [1, 1, 0, 0, 0],
        [1, 0, 1, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 1, 1],
        [0, 0, 0, 1, 1],
        [0, 0, 1, 0, 1],
    ])
    candidates = ["C0", "C1", "C2", "C3", "C4"]
    K = 2
    P = 25.0
    return {
        "weights": weights,
        "A": A,
        "candidates": candidates,
        "K": K,
        "P": P,
        "expected_optimum_coverage": 35.0,
        "expected_optimum_combos": {("C0", "C3"), ("C0", "C4")},
    }


# ===========================================================================
# 1. Exact Benchmark Instance & Exhaustive 32-State Validation
# ===========================================================================
class TestBenchmarkExhaustiveValidation:
    """Verifies that the QUBO matrix accurately models the benchmark instance."""

    def test_benchmark_matrix_properties(self, benchmark_data):
        d = benchmark_data
        qubo_res: QuboResult = build_sensor_qubo(
            coverage_matrix=d["A"],
            zone_weights=d["weights"],
            budget=d["K"],
            penalty=d["P"],
            candidate_ids=d["candidates"],
        )

        assert qubo_res.num_variables == 5
        assert qubo_res.budget == 2
        assert qubo_res.penalty == 25.0
        assert qubo_res.Q.shape == (5, 5)
        # Upper-triangular check
        assert np.all(np.tril(qubo_res.Q, -1) == 0.0)

        # Expected alpha (individual coverage):
        # C0: 10 + 7.5 = 17.5
        # C1: 10 + 5 = 15.0
        # C2: 7.5 + 5 + 5 = 17.5
        # C3: 5 + 2.5 + 10 = 17.5
        # C4: 2.5 + 10 + 5 = 17.5
        expected_alpha = np.array([17.5, 15.0, 17.5, 17.5, 17.5])
        np.testing.assert_allclose(qubo_res.alpha, expected_alpha, atol=1e-9)

        # Offset = P * K^2 = 25 * 4 = 100.0
        assert abs(qubo_res.offset - 100.0) < 1e-9

    def test_all_32_states_exhaustive_ground_truth(self, benchmark_data):
        """
        Enumerates all 2^5 = 32 binary states.
        Proves:
        A. The global minimum QUBO states are feasible.
        B. The minimum-energy feasible states match the combinatorial optimum (coverage 35.0).
        C. The optimal selections are exactly (C0, C3) and (C0, C4).
        D. No infeasible state has lower energy than the optimal feasible states.
        """
        d = benchmark_data
        qubo_res = build_sensor_qubo(
            d["A"], d["weights"], budget=d["K"], penalty=d["P"], candidate_ids=d["candidates"]
        )

        N = 5
        all_states = []
        for idx in range(1 << N):
            x = np.array([(idx >> b) & 1 for b in range(N)])
            energy = evaluate_qubo(x, qubo_res.Q, qubo_res.offset)
            actual_cov = compute_actual_coverage(x, d["A"], d["weights"])
            decoded = decode_solution(x, d["candidates"], expected_budget=d["K"])
            all_states.append({
                "x": x,
                "energy": energy,
                "actual_coverage": actual_cov,
                "decoded": decoded,
                "is_feasible": decoded["is_feasible"],
                "selected_ids": tuple(decoded["selected_candidate_ids"]),
            })

        # Sort by QUBO energy ascending
        all_states.sort(key=lambda s: s["energy"])

        min_energy = all_states[0]["energy"]
        ground_states = [s for s in all_states if abs(s["energy"] - min_energy) < 1e-9]

        # A. Ground states must be feasible
        for gs in ground_states:
            assert gs["is_feasible"] is True, f"Ground state {gs['x']} is not budget feasible!"

        # B & C. Coverage must be 35.0, and selections must be (C0, C3) or (C0, C4)
        found_selections = {gs["selected_ids"] for gs in ground_states}
        assert found_selections == d["expected_optimum_combos"]
        for gs in ground_states:
            assert abs(gs["actual_coverage"] - d["expected_optimum_coverage"]) < 1e-9
            # Ground state energy is exactly -35.0
            assert abs(gs["energy"] - (-35.0)) < 1e-9

        # D. No infeasible state has energy <= min_energy
        infeasible_states = [s for s in all_states if not s["is_feasible"]]
        assert len(infeasible_states) == 32 - 10  # 10 feasible pairs of size 2, 22 infeasible
        for inf in infeasible_states:
            assert inf["energy"] > min_energy + 1e-6, (
                f"Infeasible state {inf['x']} with budget {inf['decoded']['sensors_selected_count']} "
                f"has energy {inf['energy']} <= ground state energy {min_energy}!"
            )


# ===========================================================================
# 2. Independent Objective & Classical Alignment
# ===========================================================================
class TestIndependentObjectiveAlignment:
    """Ensures non-circular validation by comparing QUBO against direct coverage."""

    def test_direct_coverage_matches_combinatorial_brute_force(self, benchmark_data):
        d = benchmark_data
        candidates = list(range(5))

        # Direct combinatorial search over combinations of size K
        best_cov = -1.0
        best_combos = []
        for combo in itertools.combinations(candidates, d["K"]):
            x = np.zeros(5, dtype=int)
            x[list(combo)] = 1
            cov = compute_actual_coverage(x, d["A"], d["weights"])
            if cov > best_cov:
                best_cov = cov
                best_combos = [combo]
            elif abs(cov - best_cov) < 1e-9:
                best_combos.append(combo)

        assert best_cov == 35.0
        named_combos = {tuple(f"C{idx}" for idx in c) for c in best_combos}
        assert named_combos == d["expected_optimum_combos"]

    def test_solution_decoding_contract(self):
        candidate_ids = ["S0", "S1", "S2", "S3"]
        x = [1, 0, 1, 0]
        res = decode_solution(x, candidate_ids=candidate_ids, expected_budget=2)

        assert res["selected_indices"] == [0, 2]
        assert res["selected_candidate_ids"] == ["S0", "S2"]
        assert res["sensors_selected_count"] == 2
        assert res["is_feasible"] is True
        assert res["budget_error"] == 0

        # Infeasible test
        res_inf = decode_solution(x, candidate_ids=candidate_ids, expected_budget=3)
        assert res_inf["is_feasible"] is False
        assert res_inf["budget_error"] == -1


# ===========================================================================
# 3. Randomized Multi-Instance Validation
# ===========================================================================
class TestRandomizedValidation:
    """Generates varied small instances to verify QUBO ground state matches brute force."""

    @pytest.mark.parametrize("seed,N,M,K", [
        (42, 4, 6, 2),
        (101, 5, 7, 2),
        (202, 6, 8, 2),
        (303, 5, 8, 3),
        (404, 6, 6, 2),
        (505, 4, 5, 1),
    ])
    def test_random_instance_qubo_matches_exhaustive_optimum(self, seed, N, M, K):
        rng = np.random.default_rng(seed)

        # Generate non-trivial coverage matrix (density ~ 0.4)
        A = (rng.uniform(0, 1, size=(M, N)) < 0.4).astype(int)
        # Ensure every zone is covered by at least one candidate, and every candidate covers at least one zone
        for z in range(M):
            if A[z].sum() == 0:
                A[z, rng.integers(0, N)] = 1
        for c in range(N):
            if A[:, c].sum() == 0:
                A[rng.integers(0, M), c] = 1

        weights = rng.uniform(1.0, 15.0, size=M).round(1)

        # 1. Exhaustive ground truth for budget K
        best_direct_cov = -1.0
        best_feasible_combos = []
        for combo in itertools.combinations(range(N), K):
            x = np.zeros(N, dtype=int)
            x[list(combo)] = 1
            cov = compute_actual_coverage(x, A, weights)
            if cov > best_direct_cov:
                best_direct_cov = cov
                best_feasible_combos = [tuple(combo)]
            elif abs(cov - best_direct_cov) < 1e-9:
                best_feasible_combos.append(tuple(combo))

        # 2. Build QUBO
        qubo_res = build_sensor_qubo(A, weights, budget=K)

        # 3. Evaluate all 2^N states on QUBO
        all_qubo_states = []
        for idx in range(1 << N):
            x = np.array([(idx >> b) & 1 for b in range(N)])
            e = evaluate_qubo(x, qubo_res.Q, qubo_res.offset)
            cov = compute_actual_coverage(x, A, weights)
            is_feasible = bool(x.sum() == K)
            all_qubo_states.append({
                "x": x,
                "combo": tuple(np.where(x == 1)[0]),
                "energy": e,
                "coverage": cov,
                "is_feasible": is_feasible,
            })

        all_qubo_states.sort(key=lambda s: s["energy"])

        # Check feasibility of lowest energy states
        min_e = all_qubo_states[0]["energy"]
        ground_states = [s for s in all_qubo_states if abs(s["energy"] - min_e) < 1e-5]

        # Lowest energy state must be feasible
        assert ground_states[0]["is_feasible"], "QUBO ground state violated budget!"

        # The coverage of the QUBO ground state must match the exhaustive optimum
        qubo_best_cov = ground_states[0]["coverage"]
        assert abs(qubo_best_cov - best_direct_cov) < 1e-4, (
            f"Seed {seed}: QUBO best coverage ({qubo_best_cov}) != Exhaustive optimum ({best_direct_cov})"
        )


# ===========================================================================
# 4. Penalty Parameter Validation
# ===========================================================================
class TestPenaltySensitivity:
    """Verifies the theoretical condition P > max(alpha) and failure modes when P is small."""

    def test_sufficient_penalty_enforces_exact_budget(self, benchmark_data):
        d = benchmark_data
        # max(alpha) = 17.5. P = 25.0 > 17.5
        qubo_res = build_sensor_qubo(d["A"], d["weights"], budget=d["K"], penalty=25.0)

        # Test state with 3 sensors (e.g. C0, C3, C4)
        x_infeasible = np.array([1, 0, 0, 1, 1])
        energy_inf = evaluate_qubo(x_infeasible, qubo_res.Q, qubo_res.offset)

        # Test state with 2 sensors (optimal feasible C0, C3)
        x_feasible = np.array([1, 0, 0, 1, 0])
        energy_feas = evaluate_qubo(x_feasible, qubo_res.Q, qubo_res.offset)

        # Infeasible must have strictly higher energy
        assert energy_inf > energy_feas
        assert energy_inf - energy_feas >= 10.0  # Clear energy barrier

    def test_insufficient_penalty_causes_budget_overflow(self, benchmark_data):
        """
        When P is too small (e.g. P = 2.0 << max(alpha)=17.5), adding an additional sensor
        provides more coverage than the tiny penalty cost, leading the QUBO to prefer
        infeasible budget violations.
        """
        d = benchmark_data
        qubo_res_weak = build_sensor_qubo(d["A"], d["weights"], budget=d["K"], penalty=2.0)

        # Evaluate all 32 states under weak penalty
        all_states = []
        for idx in range(32):
            x = np.array([(idx >> b) & 1 for b in range(5)])
            e = evaluate_qubo(x, qubo_res_weak.Q, qubo_res_weak.offset)
            all_states.append((e, x, x.sum()))

        all_states.sort(key=lambda s: s[0])
        best_state = all_states[0]

        # Under weak penalty P=2.0, the ground state chooses more than K=2 sensors!
        assert best_state[2] > d["K"], "Expected budget overflow when penalty P is insufficient!"

    def test_borderline_penalty_boundary(self, benchmark_data):
        d = benchmark_data
        max_alpha = 17.5
        # Penalty strictly above max_alpha
        p_safe = recommend_penalty(np.array([max_alpha]), multiplier=1.1)
        assert p_safe > max_alpha


# ===========================================================================
# 5. Edge Cases & Input Validation
# ===========================================================================
class TestEdgeCasesAndValidation:
    """Verifies that invalid or boundary inputs are explicitly and gracefully handled."""

    def test_budget_equal_to_candidate_count(self):
        A = np.eye(3, dtype=int)
        w = np.array([5.0, 5.0, 5.0])
        res = build_sensor_qubo(A, w, budget=3)
        assert res.budget == 3
        # Ground state must select all 3
        x_all = [1, 1, 1]
        e_all = evaluate_qubo(x_all, res.Q, res.offset)
        x_sub = [1, 1, 0]
        e_sub = evaluate_qubo(x_sub, res.Q, res.offset)
        assert e_all < e_sub

    def test_budget_exceeds_candidates_raises_error(self):
        A = np.ones((2, 3), dtype=int)
        w = np.array([1.0, 1.0])
        with pytest.raises(ValueError, match="cannot exceed total candidate count"):
            build_sensor_qubo(A, w, budget=4)

    def test_zero_or_negative_budget_raises_error(self):
        A = np.ones((2, 3), dtype=int)
        w = np.array([1.0, 1.0])
        with pytest.raises(ValueError, match="Budget K must be >= 1"):
            build_sensor_qubo(A, w, budget=0)
        with pytest.raises(ValueError, match="Budget K must be >= 1"):
            build_sensor_qubo(A, w, budget=-2)

    def test_empty_coverage_matrix_raises_error(self):
        with pytest.raises(ValueError, match="Coverage matrix cannot be empty"):
            build_sensor_qubo(np.zeros((0, 0)), np.array([]), budget=1)

    def test_dimension_mismatch_raises_error(self):
        A = np.ones((3, 2), dtype=int)
        w = np.array([1.0, 2.0])  # length 2, but A has 3 zones
        with pytest.raises(ValueError, match="Dimension mismatch"):
            build_sensor_qubo(A, w, budget=1)

    def test_negative_zone_weights_raises_error(self):
        A = np.ones((2, 2), dtype=int)
        w = np.array([1.0, -2.5])
        with pytest.raises(ValueError, match="Zone weights must be non-negative"):
            build_sensor_qubo(A, w, budget=1)

    def test_non_binary_coverage_matrix_raises_error(self):
        A = np.array([[1, 2], [0, 1]])
        w = np.array([1.0, 1.0])
        with pytest.raises(ValueError, match="Coverage matrix entries must be strictly binary"):
            build_sensor_qubo(A, w, budget=1)

    def test_non_binary_vector_evaluation_raises_error(self):
        Q = np.eye(2)
        with pytest.raises(ValueError, match="All elements must be 0 or 1"):
            evaluate_qubo([0, 2], Q)
        with pytest.raises(ValueError, match="All elements must be 0 or 1"):
            evaluate_qubo([0.5, 0.5], Q)

    def test_single_candidate_single_zone(self):
        A = np.array([[1]])
        w = np.array([10.0])
        res = build_sensor_qubo(A, w, budget=1)
        assert res.num_variables == 1
        e1 = evaluate_qubo([1], res.Q, res.offset)
        e0 = evaluate_qubo([0], res.Q, res.offset)
        assert e1 < e0


# ===========================================================================
# 6. Domain Adapter Integration Test
# ===========================================================================
class TestDomainAdapterIntegration:
    """Verifies integration with actual QuantumFlood domain candidates and zones."""

    def test_build_from_domain_objects(self):
        from app.gis.geo_loader import get_risk_zone_geometry
        from app.optimization.candidate_generator import generate_candidates

        zones = get_risk_zone_geometry("low")[:6]  # 6 zones
        for z in zones:
            z["risk_score"] = 2.0
            z["risk_level"] = "MODERATE"
        zones[0]["risk_level"] = "CRITICAL"  # critical boost test

        candidates = generate_candidates(resolution="low")[:5]  # 5 candidates

        qubo_res = build_sensor_qubo_from_domain(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=2.5,
            budget=2,
            penalty=30.0,
        )

        assert qubo_res.num_variables == 5
        assert qubo_res.budget == 2
        assert len(qubo_res.candidate_ids) == 5
        assert qubo_res.Q.shape == (5, 5)

        # Verify evaluation
        e = evaluate_qubo([1, 1, 0, 0, 0], qubo_res.Q, qubo_res.offset)
        assert isinstance(e, float)
