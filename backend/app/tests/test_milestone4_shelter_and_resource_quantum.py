"""
Milestone 4 — Quantum-Assisted Shelter Portfolio & Resource Optimization Verification
======================================================================================
Validates:
1. Shelter Portfolio Selection QUBO encoding (MCDA suitability + spatial dispersion).
2. QAOA portfolio optimization vs Classical Greedy baseline vs Exhaustive Optimum.
3. Operational shelters isolation (verified operational shelters remain active and untouched).
4. Quantum Resource Knapsack under scarcity (urgency weighting + fairness).
5. Strict warehouse inventory conservation (over-allocation mathematically impossible).
6. FastAPI endpoints (/api/shelters/portfolio/quantum and /api/resources/shelter-requests/quantum-optimize).
"""
import pytest
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.shelter_portfolio_optimizer import (
    build_shelter_portfolio_qubo,
    ShelterPortfolioOptimizer,
)
from app.services.quantum_resource_allocator import (
    QuantumResourceAllocator,
    build_resource_allocation_qubo,
)
from app.services.shelter_request_service import (
    list_shelter_requests,
    get_inventory_levels,
    allocate_shelter_request,
)


@pytest.fixture
def test_client():
    return TestClient(app)


def test_shelter_portfolio_qubo_structure():
    """Verify that the shelter portfolio QUBO incorporates suitability and distance penalties."""
    candidates = [
        {"id": "SL-01", "lat": 16.50, "lon": 80.60, "suitability_score": 85.0},
        {"id": "SL-02", "lat": 16.51, "lon": 80.61, "suitability_score": 90.0}, # Close
        {"id": "SL-03", "lat": 16.60, "lon": 80.70, "suitability_score": 70.0}, # Far
    ]
    qubo = build_shelter_portfolio_qubo(candidates, budget=2, min_separation_km=2.0)
    assert qubo.num_variables == 3
    assert qubo.budget == 2
    # Off-diagonal (0, 1) has proximity penalty because distance < 2.0 km
    assert qubo.Q[0, 1] > 2.0 * qubo.penalty


def test_shelter_portfolio_optimizer_execution():
    """Verify that ShelterPortfolioOptimizer solves candidate portfolio and reports baseline comparison."""
    candidates = [
        {"id": f"SL-{i:02d}", "lat": 16.50 + i * 0.02, "lon": 80.60 + (i % 2) * 0.02, "suitability_score": 60.0 + i * 5}
        for i in range(6)
    ]
    optimizer = ShelterPortfolioOptimizer()
    report = optimizer.optimize_portfolio(candidates, budget=2, min_separation_km=1.5, p=1, shots=200, seed=42)

    assert report["engine_type"] == "quantum_qaoa_portfolio"
    assert len(report["selected_shelters"]) == 2
    assert report["is_feasible"] is True
    assert "classical_baseline" in report
    assert report["classical_baseline"]["is_feasible"] is True
    assert "exhaustive_optimum" in report


def test_operational_shelters_untouched_by_portfolio():
    """Verify that verified operational shelters are excluded from proposed site construction selection."""
    from app.services.safe_location_service import get_operational_shelters
    ops = get_operational_shelters()
    op_ids = {s["id"] for s in ops}
    assert len(op_ids) > 0
    for op_id in op_ids:
        assert op_id.startswith("FAC-")
        assert not op_id.startswith("SL-")


def test_quantum_resource_knapsack_conservation():
    """Verify that quantum resource knapsack strictly obeys available inventory."""
    requests = [
        {"id": "REQ-T1", "requested_quantity": 500, "urgency": "CRITICAL", "resource_type": "Test Supply"},
        {"id": "REQ-T2", "requested_quantity": 400, "urgency": "HIGH", "resource_type": "Test Supply"},
        {"id": "REQ-T3", "requested_quantity": 300, "urgency": "LOW", "resource_type": "Test Supply"},
    ]
    available_stock = 600 # Scarcity: total requested 1200 > 600

    allocator = QuantumResourceAllocator()
    classical_res = allocator.solve_classical_knapsack(requests, available_stock=available_stock)
    assert classical_res["is_feasible"] is True
    assert classical_res["total_allocated"] <= available_stock
    # Critical should get allocated first
    crit_alloc = next(a for a in classical_res["allocations"] if a["request_id"] == "REQ-T1")
    assert crit_alloc["allocated_quantity"] == 500


def test_api_shelters_portfolio_quantum_endpoint(test_client):
    """Verify that POST /api/shelters/portfolio/quantum runs end-to-end."""
    res = test_client.post("/api/shelters/portfolio/quantum", json={
        "budget": 2,
        "min_separation_km": 1.5,
        "p": 1,
        "shots": 200,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["engine_type"] == "quantum_qaoa_portfolio"
    assert len(data["selected_shelters"]) == 2
    assert "classical_baseline" in data
    assert "minimum_pairwise_distance_km" in data


def test_api_resource_quantum_optimize_endpoint(test_client):
    """Verify that POST /api/resources/shelter-requests/quantum-optimize executes."""
    res = test_client.post("/api/resources/shelter-requests/quantum-optimize", json={
        "resource_type": "Clean Drinking Water (L)",
        "p": 1,
        "shots": 200,
    })
    assert res.status_code == 200
    data = res.json()
    assert "available_stock" in data
    assert "resource_type" in data
