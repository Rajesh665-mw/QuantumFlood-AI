"""
Milestone 3: Pre-Deployment Hardening & Multi-User Readiness Regression Tests
=============================================================================
Comprehensive test suite verifying Phase 7 items 1 through 15:
 1. Concurrent requests for different study areas do not mix locations or results
 2. Concurrent analyses for the same area with different scenarios remain independent
 3. One user's reset/new area does not clear another user's stored analysis
 4. Missing required context produces an explicit error instead of silent shared-state fallback
 5. Explicit benchmark mode remains functional and isolated
 6. Analysis IDs reject malformed input and directory traversal attempts
 7. Invalid, missing, or expired analysis IDs do not return another result
 8. Reports are generated strictly from the requested analysis bundle, not global latest files
 9. Parallel report generation for separate analyses remains isolated
 10. Atomic persistence safely handles simultaneous concurrent writes without corrupting files
 11. Expired-result cleanup deletes expired analyses while leaving live ones untouched
 12. Persisted results behave correctly across process restarts (cache miss disk reload)
 13. In-memory cache LRU eviction does not cause cross-user data leakage
 14. HTTP security headers (nosniff, DENY, Referrer-Policy) are present on responses
 15. CORS policy behaves correctly according to configured origins
"""
import os
import json
import time
import shutil
import threading
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.analysis_store import AnalysisStore, analysis_store
from app.services.pipeline_state import state
from app.ml.model_manager import ModelManager


client = TestClient(app)


# ============================================================================
# 1. CONCURRENT STUDY-AREA ISOLATION
# ============================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_01_concurrent_different_study_areas_isolated(mock_waterway):
    """Two concurrent requests for different study areas do not mix locations or results."""
    tokyo_payload = {
        "rainfall_mm_24h": 55.0,
        "study_area": {
            "name": "Tokyo Delta M3",
            "center": {"lat": 35.68, "lon": 139.69},
            "bounding_box": {"min_lat": 35.63, "max_lat": 35.73, "min_lon": 139.64, "max_lon": 139.74},
            "is_default_location": False,
        }
    }
    sydney_payload = {
        "rainfall_mm_24h": 120.0,
        "study_area": {
            "name": "Sydney Harbour M3",
            "center": {"lat": -33.86, "lon": 151.20},
            "bounding_box": {"min_lat": -33.91, "max_lat": -33.81, "min_lon": 151.15, "max_lon": 151.25},
            "is_default_location": False,
        }
    }

    barrier = threading.Barrier(2)
    results = {}

    def run_req(city, payload):
        barrier.wait()
        res = client.post("/api/risk/generate", json=payload)
        results[city] = res

    t1 = threading.Thread(target=run_req, args=("tokyo", tokyo_payload))
    t2 = threading.Thread(target=run_req, args=("sydney", sydney_payload))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["tokyo"].status_code == 200
    assert results["sydney"].status_code == 200

    tokyo_data = results["tokyo"].json()
    sydney_data = results["sydney"].json()

    assert tokyo_data["analysis_id"] != sydney_data["analysis_id"]
    assert tokyo_data["study_area"]["name"] == "Tokyo Delta M3"
    assert sydney_data["study_area"]["name"] == "Sydney Harbour M3"
    assert 35.60 <= tokyo_data["study_area"]["center"]["lat"] <= 35.75
    assert -34.00 <= sydney_data["study_area"]["center"]["lat"] <= -33.70


# ============================================================================
# 2. SAME AREA, DIFFERENT SCENARIOS
# ============================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_02_same_area_different_scenarios_independent(mock_waterway):
    """Two analyses for the same area but different scenarios remain independent."""
    base_area = {
        "name": "Scenario Test Basin",
        "center": {"lat": 25.0, "lon": 85.0},
        "bounding_box": {"min_lat": 24.9, "max_lat": 25.1, "min_lon": 84.9, "max_lon": 85.1},
        "is_default_location": False,
    }

    # Low rainfall vs High rainfall
    res_low = client.post("/api/risk/generate", json={
        "study_area": base_area,
        "rainfall_mm_24h": 10.0,
        "water_level_m": 1.5,
        "inflow_ktcmd": 20.0,
    })
    res_high = client.post("/api/risk/generate", json={
        "study_area": base_area,
        "rainfall_mm_24h": 220.0,
        "water_level_m": 8.0,
        "inflow_ktcmd": 300.0,
    })

    assert res_low.status_code == 200
    assert res_high.status_code == 200

    d_low = res_low.json()
    d_high = res_high.json()

    assert d_low["analysis_id"] != d_high["analysis_id"]
    bundle_low = analysis_store.get(d_low["analysis_id"])
    bundle_high = analysis_store.get(d_high["analysis_id"])

    assert bundle_low["scenario_params"]["rainfall_mm_24h"] == 10.0
    assert bundle_high["scenario_params"]["rainfall_mm_24h"] == 220.0
    # High rainfall risk should exceed low rainfall risk
    low_max = max(z["risk_score"] for z in d_low["zones"])
    high_max = max(z["risk_score"] for z in d_high["zones"])
    assert high_max >= low_max


# ============================================================================
# 3. RESET DOES NOT CLEAR STORED ANALYSES
# ============================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_03_reset_does_not_clear_stored_analysis(mock_waterway):
    """One user's reset or location change does not clear another user's stored results."""
    user_area = {
        "name": "Isolated User Basin",
        "center": {"lat": 18.5, "lon": 73.8},
        "bounding_box": {"min_lat": 18.4, "max_lat": 18.6, "min_lon": 73.7, "max_lon": 73.9},
        "is_default_location": False,
    }

    res_user = client.post("/api/risk/generate", json={"study_area": user_area, "rainfall_mm_24h": 80.0})
    assert res_user.status_code == 200
    aid = res_user.json()["analysis_id"]

    # Another operator resets area
    res_reset = client.post("/api/area/reset")
    assert res_reset.status_code == 200

    # User's analysis in analysis_store remains 100% intact
    bundle = analysis_store.get(aid)
    assert bundle is not None
    assert bundle["study_area"]["name"] == "Isolated User Basin"


# ============================================================================
# 4. MISSING REQUIRED CONTEXT PRODUCES EXPLICIT ERROR
# ============================================================================

def test_04_missing_context_produces_explicit_error():
    """Missing required context returns an explicit validation error without silent fallback."""
    # GET /api/risk/zones without analysis_id in multi-user mode
    res = client.get("/api/risk/zones")
    assert res.status_code == 400
    assert "analysis_id" in res.json()["detail"].lower()

    # GET /api/reports for non-existent ID
    res_rep = client.get("/api/reports/ANL-0000000000000000")
    assert res_rep.status_code == 404


# ============================================================================
# 5. EXPLICIT BENCHMARK MODE FUNCTIONAL
# ============================================================================

def test_05_explicit_benchmark_mode():
    """Explicit benchmark mode remains functional and correctly labeled."""
    res = client.post("/api/risk/generate", json={
        "use_benchmark": True,
        "rainfall_mm_24h": 40.0,
        "water_level_m": 4.5,
        "inflow_ktcmd": 75.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert "Krishna" in data["study_area"]["river"] or "Vijayawada" in data["study_area"]["name"]
    assert data["study_area"]["is_default_location"] is True


# ============================================================================
# 6. ANALYSIS ID VALIDATION & PATH TRAVERSAL DEFENSE
# ============================================================================

def test_06_analysis_id_traversal_rejection():
    """Analysis IDs reject malformed inputs and directory traversal attempts."""
    url_traversal_ids = [
        "../etc/passwd",
        "..\\windows\\system32",
        "ANL-../../../etc/shadow",
        "ANL-..\\..\\config",
        "ANL-short",
        "ANL-abc$#@!invalid",
    ]

    for bad_id in url_traversal_ids:
        assert analysis_store.is_valid_id(bad_id) is False
        res = client.get(f"/api/reports/{bad_id}")
        assert res.status_code in (400, 404)

    # Directly verify store rejects null bytes and whitespace without HTTP client URL parsing error
    assert analysis_store.is_valid_id("ANL-12345\x00nullbyte") is False
    assert analysis_store.is_valid_id("") is False
    assert analysis_store.is_valid_id("   ") is False


# ============================================================================
# 7. INVALID / MISSING / EXPIRED IDS RETURN 404
# ============================================================================

def test_07_invalid_or_missing_id_returns_404():
    """Non-existent validly formatted analysis ID returns 404 and does not leak other data."""
    valid_uuid_id = "ANL-" + "f" * 32
    assert analysis_store.is_valid_id(valid_uuid_id) is True
    res = client.get(f"/api/reports/{valid_uuid_id}")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


# ============================================================================
# 8. REPORTS GENERATED STRICTLY FROM REQUESTED BUNDLE
# ============================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_08_reports_generated_strictly_from_requested_bundle(mock_waterway):
    """Reports are generated from the requested analysis bundle, not global latest files."""
    area_alpha = {
        "name": "Alpha Basin Exclusive",
        "center": {"lat": 12.0, "lon": 77.0},
        "bounding_box": {"min_lat": 11.9, "max_lat": 12.1, "min_lon": 76.9, "max_lon": 77.1},
        "is_default_location": False,
    }
    res_a = client.post("/api/risk/generate", json={"study_area": area_alpha, "rainfall_mm_24h": 45.0})
    aid_a = res_a.json()["analysis_id"]

    # Mutate legacy state to something completely different
    state.latest_risk_map = {"zones": [], "mutated": True}

    rep_res = client.get(f"/api/reports/{aid_a}?format=json")
    assert rep_res.status_code == 200
    rep_data = rep_res.json()
    assert rep_data["study_area"]["name"] == "Alpha Basin Exclusive"
    assert "mutated" not in rep_data.get("sections", {}).get("risk_assessment", {})


# ============================================================================
# 9. PARALLEL REPORT GENERATION ISOLATION
# ============================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_09_parallel_report_generation_isolation(mock_waterway):
    """Parallel report generation for separate analyses remains completely isolated."""
    area_1 = {
        "name": "Report Iso City 1",
        "center": {"lat": 40.71, "lon": -74.00},
        "bounding_box": {"min_lat": 40.66, "max_lat": 40.76, "min_lon": -74.05, "max_lon": -73.95},
        "is_default_location": False,
    }
    area_2 = {
        "name": "Report Iso City 2",
        "center": {"lat": 34.05, "lon": -118.24},
        "bounding_box": {"min_lat": 34.00, "max_lat": 34.10, "min_lon": -118.29, "max_lon": -118.19},
        "is_default_location": False,
    }

    res1 = client.post("/api/risk/generate", json={"study_area": area_1, "rainfall_mm_24h": 60.0})
    res2 = client.post("/api/risk/generate", json={"study_area": area_2, "rainfall_mm_24h": 90.0})
    aid1 = res1.json()["analysis_id"]
    aid2 = res2.json()["analysis_id"]

    barrier = threading.Barrier(2)
    reports = {}

    def fetch(name, aid):
        barrier.wait()
        r_json = client.get(f"/api/reports/{aid}?format=json")
        r_html = client.get(f"/api/reports/{aid}?format=html")
        reports[name] = (r_json.json(), r_html.text)

    t1 = threading.Thread(target=fetch, args=("c1", aid1))
    t2 = threading.Thread(target=fetch, args=("c2", aid2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    c1_json, c1_html = reports["c1"]
    c2_json, c2_html = reports["c2"]

    assert c1_json["analysis_id"] == aid1
    assert c2_json["analysis_id"] == aid2
    assert "Report Iso City 1" in c1_html
    assert "Report Iso City 2" not in c1_html
    assert "Report Iso City 2" in c2_html
    assert "Report Iso City 1" not in c2_html


# ============================================================================
# 10. ATOMIC PERSISTENCE & CONCURRENT WRITES
# ============================================================================

def test_10_atomic_persistence_concurrent_writes(tmp_path):
    """Simultaneous writes handle concurrency cleanly without partial writes or corruption."""
    store = AnalysisStore(storage_dir=Path(tmp_path), max_cache=50, ttl_hours=24.0)
    aid = store.generate_id()

    barrier = threading.Barrier(5)
    errors = []

    def writer(idx):
        barrier.wait()
        try:
            store.save(aid, {"worker": idx, "payload": "x" * 5000})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    # Data is valid JSON and readable
    loaded = store.get(aid)
    assert loaded is not None
    assert "worker" in loaded
    assert len(loaded["payload"]) == 5000


# ============================================================================
# 11. EXPIRED RESULT CLEANUP SWEEPER
# ============================================================================

def test_11_expired_result_cleanup(tmp_path):
    """Expired-result cleanup deletes expired analyses while leaving live ones untouched."""
    # Short TTL for test: 0.0001 hours ≈ 0.36 seconds
    store = AnalysisStore(storage_dir=Path(tmp_path), max_cache=50, ttl_hours=0.0001)

    expired_id = store.generate_id()
    store.save(expired_id, {"status": "expired_soon"})

    # Wait for TTL expiry
    time.sleep(0.5)

    # Active item created with long TTL
    store_long = AnalysisStore(storage_dir=Path(tmp_path), max_cache=50, ttl_hours=24.0)
    active_id = store_long.generate_id()
    store_long.save(active_id, {"status": "active_now"})

    # Run cleanup on short store
    deleted_count = store.cleanup_expired_analyses()
    assert deleted_count >= 1

    # Active ID still exists on disk
    assert store_long.get(active_id) is not None


# ============================================================================
# 12. PROCESS RESTART PERSISTENCE
# ============================================================================

def test_12_restart_loads_persisted_analysis(tmp_path):
    """Creating a fresh AnalysisStore instance loads persisted analyses from disk on cache miss."""
    store1 = AnalysisStore(storage_dir=Path(tmp_path), max_cache=10, ttl_hours=24.0)
    aid = store1.generate_id()
    store1.save(aid, {"persisted_field": "survives_restart", "value": 999})

    # Simulate process restart by instantiating new store with empty cache
    store2 = AnalysisStore(storage_dir=Path(tmp_path), max_cache=10, ttl_hours=24.0)
    assert aid not in store2._cache  # memory cache is empty

    loaded = store2.get(aid)
    assert loaded is not None
    assert loaded["persisted_field"] == "survives_restart"
    assert loaded["value"] == 999
    assert aid in store2._cache  # populated cache on miss


# ============================================================================
# 13. CACHE EVICTION DOES NOT LEAK DATA
# ============================================================================

def test_13_cache_eviction_no_leakage(tmp_path):
    """When memory LRU limit is reached, older items are evicted to disk without cross-user leakage."""
    store = AnalysisStore(storage_dir=Path(tmp_path), max_cache=2, ttl_hours=24.0)

    id1 = store.generate_id()
    id2 = store.generate_id()
    id3 = store.generate_id()

    store.save(id1, {"user": "User 1", "secret": "Token 1"})
    store.save(id2, {"user": "User 2", "secret": "Token 2"})
    # Saving id3 must evict id1 from memory cache
    store.save(id3, {"user": "User 3", "secret": "Token 3"})

    assert len(store._cache) <= 2
    assert id1 not in store._cache

    # Reloading id1 from disk succeeds and returns exact original data
    reloaded1 = store.get(id1)
    assert reloaded1["user"] == "User 1"
    assert reloaded1["secret"] == "Token 1"


# ============================================================================
# 14. HTTP SECURITY HEADERS
# ============================================================================

def test_14_security_headers_present():
    """HTTP security headers are attached to responses."""
    res = client.get("/api/health")
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


# ============================================================================
# 15. CORS POLICY AND ORIGINS
# ============================================================================

def test_15_cors_origin_policy():
    """CORS OPTIONS preflight behaves according to configured origins."""
    res = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert res.status_code in (200, 204)
    assert "access-control-allow-origin" in res.headers
