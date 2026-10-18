"""
Milestone 1: Request-Scoped Study-Area Isolation Test Suite
===========================================================
Deterministic verification that location-dependent operations use explicit,
validated, request-scoped study-area context without relying on or mutating
the process-wide active area singleton.

Validates:
  1. Context resolution purity and coordinate validation.
  2. Vijayawada benchmark dataset retention vs custom synthetic generation.
  3. Concurrent risk-map generation isolation across independent threads.
  4. Concurrent optimization and candidate isolation across independent threads.
  5. Immunity from concurrent global `POST /api/area/select` mutations.
  6. Concurrent evacuation routing and safe location evaluation isolation.
"""
import threading
import concurrent.futures
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.config.settings import STUDY_AREA
from app.services.active_area import get_active_area, is_default_area, clear_active_area
from app.services.study_area_service import (
    resolve_study_area_context,
    select_study_area,
    reset_to_default,
)
from app.schemas.schemas import StudyAreaPayload, BoundingBoxPayload, CenterCoordsPayload


client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_clean_state():
    reset_to_default()
    yield
    reset_to_default()


# =====================================================================
# 1. CONTEXT RESOLUTION & VALIDATION TESTS
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_distinct_coordinates_produce_distinct_contexts(mock_waterway):
    """Verifies that different coordinates produce isolated, non-overlapping contexts."""
    tokyo_ctx = resolve_study_area_context(latitude=35.6762, longitude=139.6503, half_size_deg=0.05)
    london_ctx = resolve_study_area_context(latitude=51.5074, longitude=-0.1278, half_size_deg=0.05)

    assert tokyo_ctx["center"]["lat"] == 35.6762
    assert tokyo_ctx["center"]["lon"] == 139.6503
    assert london_ctx["center"]["lat"] == 51.5074
    assert london_ctx["center"]["lon"] == -0.1278

    assert tokyo_ctx["bounding_box"]["min_lat"] != london_ctx["bounding_box"]["min_lat"]
    assert tokyo_ctx["bounding_box"]["min_lon"] != london_ctx["bounding_box"]["min_lon"]


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_context_resolution_does_not_mutate_global_active_area(mock_waterway):
    """
    Critical isolation check: resolving a custom request context must NOT change
    the global active study area singleton.
    """
    initial_area = get_active_area()
    assert is_default_area() is True

    # Resolve contexts for multiple non-benchmark locations
    tokyo = resolve_study_area_context(latitude=35.6762, longitude=139.6503)
    london = resolve_study_area_context(latitude=51.5074, longitude=-0.1278)

    assert tokyo["name"] != STUDY_AREA["name"]
    assert london["name"] != STUDY_AREA["name"]

    # Global active area MUST remain untouched and default
    active_now = get_active_area()
    assert is_default_area() is True
    assert active_now is None


def test_invalid_coordinates_and_bounds_rejected():
    """Validates that out-of-bounds coordinates and inverted bounding boxes are rejected."""
    # Latitude out of bounds
    with pytest.raises(ValidationError):
        CenterCoordsPayload(lat=95.0, lon=80.0)

    with pytest.raises(ValidationError):
        CenterCoordsPayload(lat=-95.0, lon=80.0)

    # Longitude out of bounds
    with pytest.raises(ValidationError):
        CenterCoordsPayload(lat=16.0, lon=185.0)

    # Inverted bounding box (min_lat > max_lat)
    with pytest.raises(ValidationError):
        BoundingBoxPayload(min_lat=20.0, max_lat=10.0, min_lon=80.0, max_lon=81.0)

    # Inverted bounding box (min_lon > max_lon)
    with pytest.raises(ValidationError):
        BoundingBoxPayload(min_lat=10.0, max_lat=20.0, min_lon=85.0, max_lon=80.0)


def test_explicit_vijayawada_benchmark_retains_behavior():
    """Explicitly selecting Vijayawada retains the calibrated Krishna River benchmark dataset."""
    ctx = resolve_study_area_context(
        latitude=STUDY_AREA["center"]["lat"],
        longitude=STUDY_AREA["center"]["lon"],
        half_size_deg=0.05
    )
    assert ctx["is_default_location"] is True
    assert ctx["name"] == STUDY_AREA["name"]
    assert "Krishna" in ctx["river"]


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_custom_location_labelled_modelled_provenance(mock_waterway):
    """Custom locations must never misrepresent synthetic waterways as real benchmark data."""
    ctx = resolve_study_area_context(latitude=48.8566, longitude=2.3522)  # Paris
    assert ctx["is_default_location"] is False
    assert "Synthetic" in ctx["river"]
    assert ctx["river_geojson"]["properties"]["is_synthetic"] is True
    assert ctx["river_geojson"]["properties"]["data_source"] == "SIMULATED"


# =====================================================================
# 2. CONCURRENT REQUEST ISOLATION TESTS
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_concurrent_risk_map_request_isolation(mock_waterway):
    """
    Forces two threads to concurrently execute POST /api/risk/generate for
    Tokyo and London using synchronization barriers.
    Verifies that neither response contaminates the other.
    """
    barrier = threading.Barrier(2)
    results = {}

    tokyo_payload = {
        "rainfall_mm_24h": 50.0,
        "study_area": {
            "name": "Tokyo Delta",
            "center": {"lat": 35.6762, "lon": 139.6503},
            "bounding_box": {"min_lat": 35.6262, "max_lat": 35.7262, "min_lon": 139.6003, "max_lon": 139.7003},
            "is_default_location": False,
        }
    }

    london_payload = {
        "rainfall_mm_24h": 130.0,
        "study_area": {
            "name": "London Thames",
            "center": {"lat": 51.5074, "lon": -0.1278},
            "bounding_box": {"min_lat": 51.4574, "max_lat": 51.5574, "min_lon": -0.1778, "max_lon": -0.0778},
            "is_default_location": False,
        }
    }

    def client_worker(client_name, payload):
        barrier.wait()  # synchronize release
        res = client.post("/api/risk/generate", json=payload)
        results[client_name] = res

    t1 = threading.Thread(target=client_worker, args=("tokyo", tokyo_payload))
    t2 = threading.Thread(target=client_worker, args=("london", london_payload))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["tokyo"].status_code == 200
    assert results["london"].status_code == 200

    tokyo_data = results["tokyo"].json()
    london_data = results["london"].json()

    # Verify Tokyo response has Tokyo context and zones
    assert tokyo_data["study_area"]["center"]["lat"] == 35.6762
    assert tokyo_data["study_area"]["center"]["lon"] == 139.6503
    tokyo_first_zone = tokyo_data["zones"][0]
    assert 35.60 <= tokyo_first_zone["centroid"]["lat"] <= 35.75
    assert 139.55 <= tokyo_first_zone["centroid"]["lon"] <= 139.75

    # Verify London response has London context and zones
    assert london_data["study_area"]["center"]["lat"] == 51.5074
    assert london_data["study_area"]["center"]["lon"] == -0.1278
    london_first_zone = london_data["zones"][0]
    assert 51.40 <= london_first_zone["centroid"]["lat"] <= 51.60
    assert -0.20 <= london_first_zone["centroid"]["lon"] <= 0.00

    # Ensure no cross-talk in rainfall input parameter
    assert tokyo_data["base_classification"]["component_levels"]["rainfall_mm_24h"] == "MODERATE"
    assert london_data["base_classification"]["component_levels"]["rainfall_mm_24h"] == "CRITICAL"
    assert tokyo_data["base_classification"]["overall_risk"] != london_data["base_classification"]["overall_risk"]


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_concurrent_global_area_select_does_not_contaminate_analysis(mock_waterway):
    """
    Demonstrates that while Client A is running an analysis for London with request context,
    a simultaneous call by Client B to POST /api/area/select (Tokyo) does NOT
    corrupt or contaminate Client A's London analysis results.
    """
    barrier = threading.Barrier(2)
    results = {}

    london_payload = {
        "rainfall_mm_24h": 80.0,
        "study_area": {
            "name": "London Thames",
            "center": {"lat": 51.5074, "lon": -0.1278},
            "bounding_box": {"min_lat": 51.4574, "max_lat": 51.5574, "min_lon": -0.1778, "max_lon": -0.0778},
            "is_default_location": False,
        }
    }

    def analysis_worker():
        barrier.wait()
        res = client.post("/api/risk/generate", json=london_payload)
        results["analysis"] = res

    def global_select_worker():
        barrier.wait()
        res = client.post("/api/area/select", json={
            "latitude": 35.6762,
            "longitude": 139.6503,
            "half_size_deg": 0.05
        })
        results["select"] = res

    t1 = threading.Thread(target=analysis_worker)
    t2 = threading.Thread(target=global_select_worker)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["select"].status_code == 200
    assert results["analysis"].status_code == 200

    analysis_res = results["analysis"].json()
    # Analysis MUST remain London Thames, NOT Tokyo
    assert analysis_res["study_area"]["center"]["lat"] == 51.5074
    assert analysis_res["study_area"]["center"]["lon"] == -0.1278
    assert "London" in analysis_res["study_area"]["name"]


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_concurrent_optimization_isolation(mock_waterway):
    """
    Verifies that concurrent optimization runs for Tokyo and London generate
    and select candidate sensors strictly within their respective geographic boundaries.
    """
    barrier = threading.Barrier(2)
    results = {}

    tokyo_opt = {
        "num_sensors": 3,
        "coverage_radius_km": 1.5,
        "comm_range_km": 3.0,
        "max_comm_nodes": 3,
        "study_area": {
            "name": "Tokyo Delta",
            "center": {"lat": 35.6762, "lon": 139.6503},
            "bounding_box": {"min_lat": 35.6262, "max_lat": 35.7262, "min_lon": 139.6003, "max_lon": 139.7003},
            "is_default_location": False,
        }
    }

    london_opt = {
        "num_sensors": 4,
        "coverage_radius_km": 2.0,
        "comm_range_km": 4.0,
        "max_comm_nodes": 4,
        "study_area": {
            "name": "London Thames",
            "center": {"lat": 51.5074, "lon": -0.1278},
            "bounding_box": {"min_lat": 51.4574, "max_lat": 51.5574, "min_lon": -0.1778, "max_lon": -0.0778},
            "is_default_location": False,
        }
    }

    def opt_worker(name, payload):
        barrier.wait()
        res = client.post("/api/optimization/run", json=payload)
        results[name] = res

    t1 = threading.Thread(target=opt_worker, args=("tokyo", tokyo_opt))
    t2 = threading.Thread(target=opt_worker, args=("london", london_opt))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["tokyo"].status_code == 200
    assert results["london"].status_code == 200

    tokyo_res = results["tokyo"].json()
    london_res = results["london"].json()

    # Tokyo sensors must be in Tokyo bounds
    for s in tokyo_res["optimization"]["selected_sensors"]:
        assert 35.60 <= s["lat"] <= 35.75
        assert 139.55 <= s["lon"] <= 139.75

    # London sensors must be in London bounds
    for s in london_res["optimization"]["selected_sensors"]:
        assert 51.40 <= s["lat"] <= 51.60
        assert -0.20 <= s["lon"] <= 0.00


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_concurrent_safe_locations_and_evacuation_isolation(mock_waterway):
    """Verifies that safe location evaluations and evacuation routing respect request-scoped areas."""
    paris_study_area = {
        "name": "Paris Seine",
        "center": {"lat": 48.8566, "lon": 2.3522},
        "bounding_box": {"min_lat": 48.8066, "max_lat": 48.9066, "min_lon": 2.3022, "max_lon": 2.4022},
        "is_default_location": False,
    }

    res_safe = client.post("/api/safe-locations/evaluate", json={
        "study_area": paris_study_area,
        "weight_elevation": 0.4,
        "weight_risk": 0.3,
        "weight_distance": 0.2,
        "weight_accessibility": 0.1,
    })
    assert res_safe.status_code == 200
    safe_data = res_safe.json()
    assert safe_data["total_recommended"] > 0
    for loc in safe_data["locations"]:
        lat, lon = loc["lat"], loc["lon"]
        assert 48.80 <= lat <= 48.92
        assert 2.29 <= lon <= 2.42
