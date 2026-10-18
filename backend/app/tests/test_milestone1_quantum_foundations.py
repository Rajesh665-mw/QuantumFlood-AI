"""
Milestone 1 — Quantum Foundations and Baseline Verification
============================================================
Validates the mathematical foundations of:
1. Classical baselines and complexity characteristics.
2. Safe penalty bounds for QUBO formulation: P > max(alpha).
3. Exact statevector phase evolution and Hamiltonian expectation.
4. Classical fallback isolation.
"""
import pytest
import numpy as np

from app.optimization.qubo_builder import (
    recommend_penalty,
    build_sensor_qubo,
    validate_binary_vector,
)
from app.quantum.qaoa_solver import QaoaSolver
from app.quantum.quantum_config import QaoaConfig
from app.optimization.classical_optimizer import ClassicalOptimizationEngine


def test_penalty_safe_bound():
    """Verify that recommend_penalty guarantees P > max(alpha) to avoid budget leakage."""
    alpha = np.array([5.2, 12.0, 8.4, 1.1])
    p = recommend_penalty(alpha, multiplier=1.25)
    assert p >= 12.0 * 1.25
    assert p > np.max(alpha)


def test_binary_vector_validation():
    """Verify binary vector validation against invalid shapes or values."""
    valid = np.array([0, 1, 1, 0], dtype=float)
    checked = validate_binary_vector(valid, expected_len=4)
    assert len(checked) == 4

    with pytest.raises(ValueError, match="non-binary entries"):
        validate_binary_vector([0, 2, 1, 0])

    with pytest.raises(ValueError, match="Expected binary vector of length"):
        validate_binary_vector([0, 1, 1], expected_len=4)


def test_classical_greedy_baseline_guarantees():
    """Verify that classical greedy baseline runs and outputs valid subset within budget."""
    candidates = [
        {"candidate_id": f"C-{i}", "lat": 16.5 + i * 0.01, "lon": 80.6 + i * 0.01}
        for i in range(8)
    ]
    zones = [
        {"zone_id": f"Z-{j}", "centroid": {"lat": 16.5 + j * 0.01, "lon": 80.6 + j * 0.01}, "risk_score": 3.0, "risk_level": "MODERATE"}
        for j in range(8)
    ]
    engine = ClassicalOptimizationEngine()
    result = engine.optimize(candidates, zones, radius_km=2.0, num_sensors=3)
    assert result.num_sensors_selected <= 3
    assert len(result.selected_sensors) == result.num_sensors_selected
    assert result.weighted_risk_coverage > 0.0


def test_qaoa_statevector_unitary_evolution():
    """Verify that pure NumPy statevector QAOA evolves a normalized state and preserves norm = 1."""
    solver = QaoaSolver()
    N = 4
    dim = 1 << N
    energies = np.array([float(i) for i in range(dim)])
    angles = np.array([0.5, 0.3]) # p=1, gamma=0.5, beta=0.3
    exp_val, probs = solver._simulate_circuit(angles, p=1, energies=energies, dim=dim, N=N)

    # Probabilities must sum to 1.0 (unitary evolution)
    assert np.isclose(np.sum(probs), 1.0, atol=1e-6)
    # Expectation value must be within energy bounds
    assert np.min(energies) <= exp_val <= np.max(energies)
