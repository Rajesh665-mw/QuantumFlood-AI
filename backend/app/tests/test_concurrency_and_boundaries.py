"""
Concurrency, Metric Consistency & Architectural Boundaries Tests
================================================================
Independent regression audit tests verifying:
  1. Thread-safety of active_area singleton under concurrent multi-threaded access.
  2. Verification of single-tenant shared state behavior (documenting that
     concurrent requests share the active study area singleton).
  3. Metric consistency: Geometric zone coverage percentage alignment between
     classical greedy and quantum QAOA optimization results.
  4. Explicit synthetic waterway provenance labelling (preventing synthetic rivers
     from being misrepresented as real geography).
"""
import concurrent.futures
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.active_area import (
    get_active_area, set_active_area, clear_active_area,
    is_default_area, get_active_bounding_box
)
from app.services.study_area_service import select_study_area, reset_to_default
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.quantum.quantum_optimizer import QuantumOptimizationEngine

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    reset_to_default()
    yield
    reset_to_default()


def test_thread_safe_concurrent_active_area_access():
    """
    Verifies that simultaneous multi-threaded reads and writes to the active_area
    singleton do not cause race condition crashes, deadlocks, or state corruption.
    """
    errors = []

    def writer_task(idx):
        try:
            cfg = {
                "name": f"Area-{idx}",
                "bounding_box": {"min_lat": float(idx), "max_lat": float(idx + 1), "min_lon": 0.0, "max_lon": 1.0},
                "center": {"lat": float(idx) + 0.5, "lon": 0.5},
            }
            set_active_area(cfg)
        except Exception as e:
            errors.append(e)

    def reader_task():
        try:
            area = get_active_area()
            bbox = get_active_bounding_box()
            is_def = is_default_area()
            if area is not None:
                assert "bounding_box" in area
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for i in range(25):
            futures.append(executor.submit(writer_task, i))
            futures.append(executor.submit(reader_task))
        concurrent.futures.wait(futures)

    assert len(errors) == 0, f"Thread-safety test encountered errors: {errors}"


def test_single_tenant_shared_state_boundary_documented():
    """
    Documents and verifies the architectural boundary:
    Because active study area is maintained as a process-level singleton,
    a location switch initiated by one client changes the active area for
    subsequent requests from all clients.
    
    This test formally documents why the application is a single-operator
    emergency command center / demonstration prototype and NOT multi-tenant SaaS.
    """
    # Initially default (Vijayawada)
    res_initial = client.get("/api/area/current")
    assert res_initial.status_code == 200
    assert res_initial.json()["is_default_location"] is True

    # User A selects Tokyo
    with patch("app.services.study_area_service.get_primary_waterway", return_value=None):
        res_user_a = client.post("/api/area/select", json={
            "latitude": 35.6762,
            "longitude": 139.6503,
            "half_size_deg": 0.05
        })
        assert res_user_a.status_code == 200
        assert res_user_a.json()["is_default_location"] is False

    # User B queries current area and map layers -> observes User A's Tokyo selection
    res_user_b = client.get("/api/area/current")
    assert res_user_b.status_code == 200
    assert res_user_b.json()["is_default_location"] is False
    assert round(res_user_b.json()["study_area"]["center"]["lat"], 2) == 35.68

    # Reset restores default for all
    client.post("/api/area/reset")
    res_after_reset = client.get("/api/area/current")
    assert res_after_reset.json()["is_default_location"] is True


def test_metric_parity_geometric_zone_coverage_percentage():
    """
    Verifies that ClassicalOptimizationEngine and QuantumOptimizationEngine
    use the exact same definition for coverage_percentage:
    percentage of total risk zones covered in the study area.
    """
    # Construct a 2-zone problem with 2 candidates
    zones = [
        {"zone_id": "Z1", "centroid": {"lat": 16.50, "lon": 80.60}, "risk_score": 10.0, "risk_level": "HIGH"},
        {"zone_id": "Z2", "centroid": {"lat": 16.51, "lon": 80.61}, "risk_score": 5.0, "risk_level": "LOW"},
    ]
    candidates = [
        {"candidate_id": "C1", "lat": 16.50, "lon": 80.60, "zone_id": "Z1", "risk_weight": 10.0},
        {"candidate_id": "C2", "lat": 16.51, "lon": 80.61, "zone_id": "Z2", "risk_weight": 5.0},
    ]

    c_engine = ClassicalOptimizationEngine()
    q_engine = QuantumOptimizationEngine()

    # Selecting 1 sensor that covers Z1 (1 out of 2 zones = 50.0%)
    c_res = c_engine.optimize(candidates, zones, radius_km=0.2, num_sensors=1)
    q_res, _ = q_engine.optimize(candidates, zones, coverage_radius_km=0.2, num_sensors=1, p=1, shots=100)

    # Both must report 50.0% geometric zone coverage percentage
    assert c_res.coverage_percentage == 50.0
    assert q_res.coverage_percentage == 50.0
    assert c_res.num_sensors_selected == 1
    assert q_res.num_sensors_selected == 1


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_synthetic_waterway_never_misrepresented_as_real(mock_waterway):
    """
    Verifies that when no real OSM waterway is found, the generated river
    is explicitly labelled as synthetic in both its name and metadata.
    """
    res = select_study_area(latitude=10.0, longitude=20.0, half_size_deg=0.05)
    assert res["status"] == "OK"
    sa = res["study_area"]
    river_feature = sa["river_geojson"]

    assert river_feature["properties"]["is_synthetic"] is True
    assert river_feature["properties"]["data_source"] == "SIMULATED"
    assert "Synthetic" in river_feature["properties"]["name"]
    assert "Synthetic" in sa["river"]
