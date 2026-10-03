"""
Independent Quantum & QUBO Audit Regression Tests for QuantumFlood AI.
Tests first-principles mathematical properties:
- Exact Rosenberg reduction
- Upper-triangular QUBO scalar vs matrix evaluation
- SciPy matrix exponential (expm) unitary validation against QaoaSolver statevector
- Bitstring decoding and auxiliary variable separation
- API validation boundaries and classical fallback resilience
"""

import pytest
import numpy as np
from scipy.linalg import expm
from fastapi.testclient import TestClient

from app.main import app
from app.services.pipeline_state import state
from app.optimization.qubo_builder import (
    build_sensor_qubo,
    build_exact_sensor_qubo,
    evaluate_qubo,
)
from app.quantum.quantum_config import QaoaConfig
from app.quantum.qaoa_solver import QaoaSolver


class TestIndependentQuboMathematics:
    """First-principles verification of QUBO objective and penalty functions."""

    def test_upper_triangular_matrix_convention(self):
        """Verify that x^T Q x matches sum_i Q_ii x_i + sum_{i<j} Q_ij x_i x_j exactly."""
        n_c, n_z, k = 4, 3, 2
        np.random.seed(42)
        # shape (M, N) = (zones, candidates)
        cov = (np.random.rand(n_z, n_c) > 0.4).astype(int)
        weights = np.array([10.0, 20.0, 15.0])

        qubo_data = build_sensor_qubo(cov, weights, budget=k, penalty=15.0)
        Q = qubo_data.Q
        offset = qubo_data.offset
        N = Q.shape[0]

        # Verify Q is strictly upper triangular (no lower triangular leakage)
        assert np.allclose(np.tril(Q, -1), 0.0), "Q matrix contains non-zero lower triangular entries"

        # Check for 20 random binary states
        for _ in range(20):
            x = np.random.randint(0, 2, size=N)
            e_matrix = float(x @ Q @ x) + offset
            e_scalar = offset
            for i in range(N):
                e_scalar += Q[i, i] * x[i]
                for j in range(i + 1, N):
                    e_scalar += Q[i, j] * x[i] * x[j]
            e_func = evaluate_qubo(x, Q, offset)

            assert abs(e_matrix - e_scalar) < 1e-12, f"Matrix convention mismatch: {e_matrix} vs {e_scalar}"
            assert abs(e_matrix - e_func) < 1e-12, f"Function evaluate_qubo mismatch: {e_matrix} vs {e_func}"

    def test_rosenberg_auxiliary_reduction(self):
        """Independently verify min_u H(x, u) == H_orig(x) across all states."""
        # Zone covered by C0, C1, C2 (3-way product x0*x1*x2), shape (1, 3)
        cov = np.ones((1, 3), dtype=int)
        weights = np.array([20.0])
        exact_res = build_exact_sensor_qubo(cov, weights, budget=2, penalty=25.0)

        Q_full = exact_res.Q
        offset = exact_res.offset
        assert Q_full.shape[0] == 4, f"Expected 3 candidates + 1 auxiliary = 4 qubits, got {Q_full.shape[0]}"

        # Enumerate all 8 primary states (x0, x1, x2)
        for idx in range(8):
            x0 = (idx >> 2) & 1
            x1 = (idx >> 1) & 1
            x2 = idx & 1
            x_prim = np.array([x0, x1, x2])

            # True set union coverage
            true_cov = 20.0 if np.any(x_prim == 1) else 0.0
            true_budget_pen = 25.0 * ((np.sum(x_prim) - 2) ** 2)
            true_target = -true_cov + true_budget_pen

            # Evaluate QUBO minimized over auxiliary u in {0, 1}
            e_u0 = evaluate_qubo([x0, x1, x2, 0], Q_full, offset)
            e_u1 = evaluate_qubo([x0, x1, x2, 1], Q_full, offset)
            min_qubo_e = min(e_u0, e_u1)

            diff = abs(min_qubo_e - true_target)
            assert diff < 1e-6, f"State {x_prim}: min_u H(x, u)={min_qubo_e} != true_target={true_target}"


class TestIndependentQaoaPhysics:
    """Independent verification of QAOA unitaries against SciPy matrix exponentials."""

    def test_qaoa_unitary_evolution_vs_scipy_expm(self):
        """Compare QaoaSolver statevector against exact matrix exponentiation."""
        # (zones, candidates) = (3, 3)
        cov = np.array([
            [1, 0, 1],
            [0, 1, 1],
            [1, 1, 0],
        ], dtype=int)
        weights = np.array([10.0, 15.0, 20.0])
        qubo_data = build_sensor_qubo(cov, weights, budget=2, penalty=15.0)
        Q = qubo_data.Q
        offset = qubo_data.offset
        N = Q.shape[0]

        solver = QaoaSolver(QaoaConfig(p=1, shots=1024, seed=42))

        # Build diagonal Cost Hamiltonian matrix
        dim = 2 ** N
        H_C_diag = np.zeros(dim, dtype=float)
        for s in range(dim):
            bits = np.array([(s >> (N - 1 - i)) & 1 for i in range(N)])
            H_C_diag[s] = float(bits @ Q @ bits) + offset
        H_C = np.diag(H_C_diag)

        # Build Mixer Hamiltonian matrix H_M = sum_i X_i
        sigma_x = np.array([[0, 1], [1, 0]], dtype=complex)
        I2 = np.eye(2, dtype=complex)

        H_M = np.zeros((dim, dim), dtype=complex)
        for i in range(N):
            term = 1.0
            for j in range(N):
                op = sigma_x if j == i else I2
                term = np.kron(term, op) if isinstance(term, np.ndarray) else op
            H_M += term

        gamma, beta = 0.35, 0.65
        U_C = expm(-1j * gamma * H_C)
        U_M = expm(-1j * beta * H_M)

        psi_0 = np.ones(dim, dtype=complex) / np.sqrt(dim)
        psi_ref = U_M @ U_C @ psi_0
        probs_ref = np.abs(psi_ref) ** 2

        # Statevector from project's QaoaSolver simulation
        _, energies = solver._precompute_basis_and_energies(Q, offset)
        angles = np.array([gamma, beta])
        exp_val_solver, probs_solver = solver._simulate_circuit(angles, p=1, energies=energies, dim=dim, N=N)

        max_prob_diff = np.max(np.abs(probs_ref - probs_solver))
        assert max_prob_diff < 1e-12, f"Statevector probability divergence: {max_prob_diff}"

        # Expectation values match
        E_ref = float(np.sum(probs_ref * H_C_diag))
        assert abs(E_ref - exp_val_solver) < 1e-12, f"Expectation value divergence: {E_ref} vs {exp_val_solver}"

    def test_bitstring_decoding_and_aux_separation(self):
        """Verify candidate decoding correctly extracts primary sensors and separates auxiliaries."""
        cov = np.ones((1, 3), dtype=int)
        weights = np.array([20.0])
        c_names = ["C-000", "C-001", "C-002"]

        solver = QaoaSolver(QaoaConfig(p=1, shots=512, seed=42, formulation_mode="exact"))
        res = solver.optimize(
            coverage_matrix=cov,
            zone_weights=weights,
            budget=2,
            candidate_ids=c_names,
        )

        assert res.is_feasible is True
        assert res.sensors_selected_count == 2
        for cid in res.selected_candidate_ids:
            assert cid in c_names


class TestApiValidationAndClassicalFallback:
    """Break-testing input validation and ensuring quantum failures do not degrade classical system."""

    def setup_method(self):
        self.client = TestClient(app)
        state.latest_risk_map = {
            "resolution": "default",
            "base_classification": {"overall_risk": "HIGH", "explanation": "Audit baseline test"},
            "zones": [
                {
                    "zone_id": f"Z{i:02d}",
                    "centroid": {"lat": 16.50 + i * 0.01, "lon": 80.60 + i * 0.01},
                    "risk_score": 10.0,
                    "risk_level": "HIGH",
                }
                for i in range(6)
            ],
        }

    def test_api_rejections_and_boundaries(self):
        # K <= 0 rejected
        res = self.client.post("/api/optimization/quantum", json={"num_sensors": 0, "coverage_radius_km": 2.5})
        assert res.status_code == 422

        # p > 5 rejected
        res = self.client.post("/api/optimization/quantum", json={"num_sensors": 2, "coverage_radius_km": 2.5, "p": 6})
        assert res.status_code == 422

        # max_candidates > 16 rejected
        res = self.client.post("/api/optimization/quantum", json={"num_sensors": 2, "coverage_radius_km": 2.5, "max_candidates": 20})
        assert res.status_code == 422

    def test_classical_fallback_isolation(self):
        """Simulate a fatal crash in QaoaSolver; classical endpoint must continue operating 100%."""
        orig_solve = QaoaSolver.solve

        def faulty_solve(*args, **kwargs):
            raise RuntimeError("Fatal simulator memory fault")

        QaoaSolver.solve = faulty_solve
        try:
            # Quantum endpoint isolates error with clean 500
            q_res = self.client.post("/api/optimization/quantum", json={"num_sensors": 2, "coverage_radius_km": 2.5})
            assert q_res.status_code == 500
            assert "Fatal simulator memory fault" in q_res.json()["detail"]

            # Classical optimizer remains 100% operational
            c_res = self.client.post(
                "/api/optimization/run",
                json={"num_sensors": 4, "coverage_radius_km": 2.5, "comm_range_km": 4.0, "max_comm_nodes": 4},
            )
            assert c_res.status_code == 200
            assert c_res.json()["optimization"]["num_sensors_selected"] > 0
        finally:
            QaoaSolver.solve = orig_solve
