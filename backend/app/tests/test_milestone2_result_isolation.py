"""
Milestone 2: Request-Scoped Pipeline State, Result Isolation & Report Safety Test Suite
=====================================================================================
Deterministic verification that analysis results, follow-up operations, and report
generation remain strictly isolated per request/analysis_id and cannot contaminate
or overwrite concurrent user workflows.

Tests:
  Test A — Independent risk results (overlapping threads for distinct areas)
  Test B — Same location, different scenarios (distinct parameters & analysis_ids)
  Test C — Risk-to-optimization isolation (concurrent workflows with barrier sync)
  Test D — Evacuation and safe-location isolation (cross-area concurrent isolation)
  Test E — Report isolation (concurrent reports verified for distinct analysis data)
  Test F — Reset and location-change isolation (global reset does not wipe analysis store)
  Test G — Missing context handling (unknown analysis_id rejects with 404, benchmark preserved)
  Test H — Result identifier validation (traversal attacks, malformed IDs rejected)
"""
import threading
import concurrent.futures
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.study_area_service import reset_to_default
from app.services.analysis_store import analysis_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_environment():
    reset_to_default()
    yield
    reset_to_default()


# =====================================================================
# Test A — Independent risk results
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_a_independent_risk_results(mock_waterway):
    """
    Run overlapping risk analyses for two different study areas with different parameters.
    Verify that each result contains the correct location, parameters, and risk output.
    """
    barrier = threading.Barrier(2)
    results = {}

    tokyo_area = {
        "name": "Tokyo Test Basin",
        "region": "Kanto",
        "bounding_box": {"min_lat": 35.6, "max_lat": 35.7, "min_lon": 139.6, "max_lon": 139.7},
        "center": {"lat": 35.65, "lon": 139.65},
        "river": "Sumida River",
        "reference_gauge": "Tokyo Central",
    }
    london_area = {
        "name": "London Test Basin",
        "region": "Greater London",
        "bounding_box": {"min_lat": 51.45, "max_lat": 51.55, "min_lon": -0.15, "max_lon": -0.05},
        "center": {"lat": 51.50, "lon": -0.10},
        "river": "River Thames",
        "reference_gauge": "Tower Pier",
    }

    def run_user_tokyo():
        barrier.wait()
        res = client.post("/api/risk/generate", json={
            "study_area": tokyo_area,
            "rainfall_mm_24h": 120.0,
            "water_level_m": 8.0,
            "inflow_ktcmd": 200.0,
        })
        results["tokyo"] = res

    def run_user_london():
        barrier.wait()
        res = client.post("/api/risk/generate", json={
            "study_area": london_area,
            "rainfall_mm_24h": 40.0,
            "water_level_m": 4.5,
            "inflow_ktcmd": 80.0,
        })
        results["london"] = res

    t1 = threading.Thread(target=run_user_tokyo)
    t2 = threading.Thread(target=run_user_london)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    res_t = results["tokyo"]
    res_l = results["london"]

    assert res_t.status_code == 200
    assert res_l.status_code == 200

    data_t = res_t.json()
    data_l = res_l.json()

    assert data_t["analysis_id"] != data_l["analysis_id"]
    assert data_t["study_area"]["name"] == "Tokyo Test Basin"
    assert data_l["study_area"]["name"] == "London Test Basin"

    # Verify risk outputs and coordinates are strictly separated
    t_lats = [z["centroid"]["lat"] for z in data_t["zones"]]
    l_lats = [z["centroid"]["lat"] for z in data_l["zones"]]
    assert all(35.0 <= lat <= 36.5 for lat in t_lats)
    assert all(51.0 <= lat <= 52.0 for lat in l_lats)



# =====================================================================
# Test B — Same location, different scenarios
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_b_same_location_different_scenarios(mock_waterway):
    """
    Run two analyses for the same study area with different rainfall or scenario inputs.
    Verify that each result retains its own scenario parameters and results.
    """
    barrier = threading.Barrier(2)
    results = {}

    area = {
        "name": "Bengaluru City Basin",
        "region": "Karnataka",
        "bounding_box": {"min_lat": 12.9, "max_lat": 13.0, "min_lon": 77.5, "max_lon": 77.6},
        "center": {"lat": 12.97, "lon": 77.59},
        "river": "Vrishabhavathi",
        "reference_gauge": "City Station",
    }

    def run_mild_scenario():
        barrier.wait()
        res = client.post("/api/risk/generate", json={
            "study_area": area,
            "rainfall_mm_24h": 15.0,
            "water_level_m": 3.0,
            "inflow_ktcmd": 50.0,
        })
        results["mild"] = res

    def run_severe_scenario():
        barrier.wait()
        res = client.post("/api/risk/generate", json={
            "study_area": area,
            "rainfall_mm_24h": 220.0,
            "water_level_m": 12.0,
            "inflow_ktcmd": 500.0,
        })
        results["severe"] = res

    t1 = threading.Thread(target=run_mild_scenario)
    t2 = threading.Thread(target=run_severe_scenario)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    res_mild = results["mild"].json()
    res_severe = results["severe"].json()

    assert res_mild["analysis_id"] != res_severe["analysis_id"]

    mild_mean_risk = sum(z["risk_score"] for z in res_mild["zones"]) / len(res_mild["zones"])
    severe_mean_risk = sum(z["risk_score"] for z in res_severe["zones"]) / len(res_severe["zones"])

    assert severe_mean_risk > mild_mean_risk
    assert res_severe["critical_zone_count"] >= res_mild["critical_zone_count"]

    # Verify both analyses are preserved independently in analysis_store
    bundle_mild = analysis_store.get(res_mild["analysis_id"])
    bundle_severe = analysis_store.get(res_severe["analysis_id"])

    assert bundle_mild is not None
    assert bundle_severe is not None
    assert bundle_mild["scenario_params"]["rainfall_mm_24h"] == 15.0
    assert bundle_severe["scenario_params"]["rainfall_mm_24h"] == 220.0



# =====================================================================
# Test C — Risk-to-optimization isolation
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_c_risk_to_optimization_isolation(mock_waterway):
    """
    Have two concurrent workflows generate different risk maps and then execute optimization.
    Verify that each optimization uses the risk map belonging to its own analysis.
    """
    area_a = {
        "name": "Basin Alpha",
        "region": "Region A",
        "bounding_box": {"min_lat": 10.0, "max_lat": 10.1, "min_lon": 20.0, "max_lon": 20.1},
        "center": {"lat": 10.05, "lon": 20.05},
        "river": "Alpha River",
        "reference_gauge": "Alpha 1",
    }
    area_b = {
        "name": "Basin Beta",
        "region": "Region B",
        "bounding_box": {"min_lat": 30.0, "max_lat": 30.1, "min_lon": 40.0, "max_lon": 40.1},
        "center": {"lat": 30.05, "lon": 40.05},
        "river": "Beta River",
        "reference_gauge": "Beta 1",
    }

    # Step 1: Generate risk for both
    res_a = client.post("/api/risk/generate", json={"study_area": area_a, "rainfall_mm_24h": 50.0})
    res_b = client.post("/api/risk/generate", json={"study_area": area_b, "rainfall_mm_24h": 150.0})
    aid_a = res_a.json()["analysis_id"]
    aid_b = res_b.json()["analysis_id"]

    barrier = threading.Barrier(2)
    opt_results = {}

    def run_opt_a():
        barrier.wait()
        res = client.post("/api/optimization/run", json={
            "analysis_id": aid_a,
            "num_sensors": 4,
            "coverage_radius_km": 2.0,
            "comm_range_km": 5.0,
            "max_comm_nodes": 2,
        })
        opt_results["a"] = res

    def run_opt_b():
        barrier.wait()
        res = client.post("/api/optimization/run", json={
            "analysis_id": aid_b,
            "num_sensors": 6,
            "coverage_radius_km": 1.5,
            "comm_range_km": 4.0,
            "max_comm_nodes": 3,
        })
        opt_results["b"] = res

    t1 = threading.Thread(target=run_opt_a)
    t2 = threading.Thread(target=run_opt_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert opt_results["a"].status_code == 200
    assert opt_results["b"].status_code == 200

    data_a = opt_results["a"].json()
    data_b = opt_results["b"].json()

    assert data_a["analysis_id"] == aid_a
    assert data_b["analysis_id"] == aid_b

    # Verify sensor coordinates belong to their respective bounding boxes
    sensors_a = data_a["optimization"]["selected_sensors"]
    sensors_b = data_b["optimization"]["selected_sensors"]

    assert all(9.9 <= s["lat"] <= 10.2 and 19.9 <= s["lon"] <= 20.2 for s in sensors_a)
    assert all(29.9 <= s["lat"] <= 30.2 and 39.9 <= s["lon"] <= 40.2 for s in sensors_b)

    # Verify stored recommendations in analysis_store match their respective analysis
    bundle_a = analysis_store.get(aid_a)
    bundle_b = analysis_store.get(aid_b)
    assert bundle_a["optimization"]["num_sensors_requested"] == 4
    assert bundle_b["optimization"]["num_sensors_requested"] == 6


# =====================================================================
# Test D — Evacuation and safe-location isolation
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_d_evacuation_and_safe_location_isolation(mock_waterway):
    """
    Run overlapping evacuation and safe-location workflows for different areas.
    Verify that routes, facilities, geometry, and provenance are associated with the correct study area.
    """
    area_c = {
        "name": "Area Delta",
        "region": "North",
        "bounding_box": {"min_lat": 16.5, "max_lat": 16.6, "min_lon": 80.6, "max_lon": 80.7},
        "center": {"lat": 16.52, "lon": 80.62},
        "river": "Delta Channel",
        "reference_gauge": "Delta North",
    }
    area_d = {
        "name": "Area Epsilon",
        "region": "South",
        "bounding_box": {"min_lat": 12.0, "max_lat": 12.1, "min_lon": 75.0, "max_lon": 75.1},
        "center": {"lat": 12.05, "lon": 75.05},
        "river": "Epsilon Stream",
        "reference_gauge": "South Gauge",
    }

    # Generate risk for both
    res_c = client.post("/api/risk/generate", json={"study_area": area_c, "rainfall_mm_24h": 70.0})
    res_d = client.post("/api/risk/generate", json={"study_area": area_d, "rainfall_mm_24h": 90.0})
    aid_c = res_c.json()["analysis_id"]
    aid_d = res_d.json()["analysis_id"]

    barrier = threading.Barrier(2)
    evac_results = {}
    safe_results = {}

    def run_workflow_c():
        barrier.wait()
        safe_res = client.post("/api/safe-locations/evaluate", json={"analysis_id": aid_c})
        safe_results["c"] = safe_res
        evac_res = client.post("/api/evacuation/route", json={
            "analysis_id": aid_c,
            "origin_lat": 16.51,
            "origin_lon": 80.61,
            "dest_lat": 16.58,
            "dest_lon": 80.68,
        })
        evac_results["c"] = evac_res

    def run_workflow_d():
        barrier.wait()
        safe_res = client.post("/api/safe-locations/evaluate", json={"analysis_id": aid_d})
        safe_results["d"] = safe_res
        evac_res = client.post("/api/evacuation/route", json={
            "analysis_id": aid_d,
            "origin_lat": 12.01,
            "origin_lon": 75.01,
            "dest_lat": 12.08,
            "dest_lon": 75.08,
        })
        evac_results["d"] = evac_res

    t1 = threading.Thread(target=run_workflow_c)
    t2 = threading.Thread(target=run_workflow_d)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert safe_results["c"].status_code == 200
    assert safe_results["d"].status_code == 200
    assert evac_results["c"].status_code == 200
    assert evac_results["d"].status_code == 200

    sc = safe_results["c"].json()
    sd = safe_results["d"].json()
    assert sc["analysis_id"] == aid_c
    assert sd["analysis_id"] == aid_d

    # Safe locations for area C must be around 16.5 lat, area D around 12.0 lat
    for loc in sc["locations"]:
        assert 16.4 <= loc["lat"] <= 16.7
    for loc in sd["locations"]:
        assert 11.9 <= loc["lat"] <= 12.2

    ec = evac_results["c"].json()
    ed = evac_results["d"].json()
    assert ec["analysis_id"] == aid_c
    assert ed["analysis_id"] == aid_d


# =====================================================================
# Test E — Report isolation
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_e_report_isolation(mock_waterway):
    """
    Generate or prepare two distinct analyses and request reports concurrently.
    Verify that each report contains only the selected analysis's outputs and metadata.
    """
    area_1 = {
        "name": "Report Area One",
        "region": "Northern Valley",
        "bounding_box": {"min_lat": 28.5, "max_lat": 28.6, "min_lon": 77.2, "max_lon": 77.3},
        "center": {"lat": 28.55, "lon": 77.25},
        "river": "Yamuna Sector",
        "reference_gauge": "Okhla Point",
    }
    area_2 = {
        "name": "Report Area Two",
        "region": "Coastal Marsh",
        "bounding_box": {"min_lat": 13.0, "max_lat": 13.1, "min_lon": 80.2, "max_lon": 80.3},
        "center": {"lat": 13.05, "lon": 80.25},
        "river": "Cooum Sector",
        "reference_gauge": "Marina Point",
    }

    # Setup complete analyses
    res1 = client.post("/api/risk/generate", json={"study_area": area_1, "rainfall_mm_24h": 65.0})
    aid1 = res1.json()["analysis_id"]
    client.post("/api/optimization/run", json={"analysis_id": aid1, "num_sensors": 4, "coverage_radius_km": 2.0})

    res2 = client.post("/api/risk/generate", json={"study_area": area_2, "rainfall_mm_24h": 145.0})
    aid2 = res2.json()["analysis_id"]
    client.post("/api/optimization/run", json={"analysis_id": aid2, "num_sensors": 7, "coverage_radius_km": 1.8})

    barrier = threading.Barrier(2)
    reports = {}

    def fetch_report_1():
        barrier.wait()
        rep_json = client.get(f"/api/reports/{aid1}?format=json")
        rep_html = client.get(f"/api/reports/{aid1}?format=html")
        reports["r1"] = (rep_json, rep_html)

    def fetch_report_2():
        barrier.wait()
        rep_json = client.get(f"/api/reports/{aid2}?format=json")
        rep_html = client.get(f"/api/reports/{aid2}?format=html")
        reports["r2"] = (rep_json, rep_html)

    t1 = threading.Thread(target=fetch_report_1)
    t2 = threading.Thread(target=fetch_report_2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    r1_json, r1_html = reports["r1"]
    r2_json, r2_html = reports["r2"]

    assert r1_json.status_code == 200
    assert r2_json.status_code == 200
    assert r1_html.status_code == 200
    assert r2_html.status_code == 200

    d1 = r1_json.json()
    d2 = r2_json.json()

    assert d1["analysis_id"] == aid1
    assert d2["analysis_id"] == aid2
    assert d1["study_area"]["name"] == "Report Area One"
    assert d2["study_area"]["name"] == "Report Area Two"

    assert d1["sections"]["sensor_optimization"]["sensors_requested"] == 4
    assert d2["sections"]["sensor_optimization"]["sensors_requested"] == 7

    # Verify HTML contents include respective names and don't leak other report's data
    h1 = r1_html.text
    h2 = r2_html.text
    assert "Report Area One" in h1
    assert "Report Area Two" not in h1
    assert "Report Area Two" in h2
    assert "Report Area One" not in h2


# =====================================================================
# Test F — Reset and location-change isolation
# =====================================================================

@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_f_reset_and_location_change_isolation(mock_waterway):
    """
    While one analysis is in progress, have another client change or reset its study area.
    Verify that the first analysis's intermediate results and report inputs remain intact.
    """
    custom_area = {
        "name": "Persistent Client Area",
        "region": "Western Ghats",
        "bounding_box": {"min_lat": 15.0, "max_lat": 15.1, "min_lon": 74.0, "max_lon": 74.1},
        "center": {"lat": 15.05, "lon": 74.05},
        "river": "Kali River",
        "reference_gauge": "Ghat Gauge",
    }

    # Client A creates an analysis
    res_a = client.post("/api/risk/generate", json={"study_area": custom_area, "rainfall_mm_24h": 85.0})
    aid_a = res_a.json()["analysis_id"]
    client.post("/api/optimization/run", json={"analysis_id": aid_a, "num_sensors": 5})

    # Client B resets to default or changes area
    res_reset = client.post("/api/area/reset")
    assert res_reset.status_code == 200

    # Client A continues follow-up work using its analysis_id
    res_recs = client.get(f"/api/recommendations?analysis_id={aid_a}")
    assert res_recs.status_code == 200
    recs = res_recs.json()
    assert "recommendations" in recs or isinstance(recs, list)

    res_opt = client.get(f"/api/optimization/results?analysis_id={aid_a}")
    assert res_opt.status_code == 200
    assert res_opt.json()["analysis_id"] == aid_a

    # Client A requests its report
    rep = client.get(f"/api/reports/{aid_a}?format=json")
    assert rep.status_code == 200
    assert rep.json()["study_area"]["name"] == "Persistent Client Area"


# =====================================================================
# Test G — Missing context handling
# =====================================================================

def test_g_missing_context_handling():
    """
    Verify that an endpoint cannot silently consume another user's latest result
    or silently use the global active area when required context is missing.
    Verify that explicit benchmark mode remains functional.
    """
    # Requesting report with nonexistent analysis_id must return 404
    res = client.get("/api/reports/ANL-nonexistent123")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

    # Benchmark explicitly requested via Vijayawada coordinates works cleanly
    res_bench = client.post("/api/risk/generate", json={
        "rainfall_mm_24h": 35.0,
        "water_level_m": 4.0,
        "inflow_ktcmd": 60.0,
    })
    assert res_bench.status_code == 200
    assert "Krishna" in res_bench.json()["study_area"]["river"] or "Vijayawada" in res_bench.json()["study_area"]["name"]


# =====================================================================
# Test H — Result identifier validation
# =====================================================================

def test_h_result_identifier_validation():
    """
    Test unknown identifiers, malformed identifiers, path traversal attempts,
    and attempts to access results outside permitted scope.
    """
    # 1. Path traversal and malformed ID validation
    traversal_ids = [
        "../etc/passwd",
        "..\\..\\windows\\system32",
        "ANL-../../../secret",
        "ANL-test/../../evil",
        "invalid_prefix_12345",
        "ANL-short",  # < 8 chars after prefix
    ]

    for bad_id in traversal_ids:
        res = client.get(f"/api/reports/{bad_id}")
        assert res.status_code in (400, 404)

        res_post = client.post("/api/reports/generate", json={"analysis_id": bad_id})
        assert res_post.status_code in (400, 404)

    # Directly verify analysis_store path security against null bytes and arbitrary paths
    assert analysis_store.is_valid_id("ANL-123\x00malicious") is False
    assert analysis_store.is_valid_id("ANL-../../../etc/passwd") is False

    # 2. Optimization with nonexistent analysis_id returns 404
    res_opt_bad = client.post("/api/optimization/run", json={"analysis_id": "ANL-doesnotexist999"})
    assert res_opt_bad.status_code == 404
