"""
Comprehensive Functional Integrity & Domain Invariant Test Suite
================================================================
Validates critical business logic, domain rules, conservation laws,
input validation, output geometry constraints, and session isolation.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.shelter_request_service import reset_shelter_logistics

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Inventory Conservation, Repeated Requests & Audit Logging
# ---------------------------------------------------------------------------

def test_inventory_conservation_and_repeat_allocations():
    """
    Validates that:
    1. Multiple requests for the same commodity consume inventory additively.
    2. Over-allocating beyond available stock is rejected with HTTP 400.
    3. Fulfillment cannot exceed allocation.
    4. Audit log records all allocation and fulfillment transitions.
    """
    reset_shelter_logistics()

    # Read starting inventory for Emergency Food Rations (Packs)
    inv_start = client.get("/api/resources/inventory").json()["inventory"]
    item_info = next(i for i in inv_start if "Emergency Food Rations" in i["item"])
    initial_stock = item_info["available"]
    item_name = item_info["item"]
    assert initial_stock > 10, "Need sufficient initial stock for test"

    # Create Request 1
    req1 = client.post("/api/safe-locations/requests", json={
        "shelter_id": "FAC-TEST-INV1",
        "shelter_name": "Camp Alpha",
        "resource_type": item_name,
        "requested_quantity": 5,
        "urgency": "HIGH",
    }).json()["request"]

    # Create Request 2
    req2 = client.post("/api/safe-locations/requests", json={
        "shelter_id": "FAC-TEST-INV2",
        "shelter_name": "Camp Beta",
        "resource_type": item_name,
        "requested_quantity": 8,
        "urgency": "CRITICAL",
    }).json()["request"]

    # Allocate Request 1 (5 units)
    alloc1 = client.post("/api/resources/allocate-request", json={
        "request_id": req1["id"],
        "allocated_quantity": 5,
    })
    assert alloc1.status_code == 200

    # Allocate Request 2 (8 units)
    alloc2 = client.post("/api/resources/allocate-request", json={
        "request_id": req2["id"],
        "allocated_quantity": 8,
    })
    assert alloc2.status_code == 200

    # Verify inventory decreased by exactly 13 units
    inv_mid = client.get("/api/resources/inventory").json()["inventory"]
    mid_stock = next(i["available"] for i in inv_mid if i["item"] == item_name)
    assert mid_stock == initial_stock - 13

    # Attempt to over-allocate beyond remaining stock
    req3 = client.post("/api/safe-locations/requests", json={
        "shelter_id": "FAC-TEST-INV3",
        "shelter_name": "Camp Gamma",
        "resource_type": item_name,
        "requested_quantity": mid_stock + 100,
        "urgency": "CRITICAL",
    }).json()["request"]

    over_res = client.post("/api/resources/allocate-request", json={
        "request_id": req3["id"],
        "allocated_quantity": mid_stock + 1,
    })
    assert over_res.status_code == 400
    assert "stock" in over_res.json()["detail"].lower()

    # Test fulfillment: over-fulfillment must fail
    over_ful = client.post("/api/resources/fulfill-request", json={
        "request_id": req1["id"],
        "fulfilled_quantity": 6,  # allocated was 5
    })
    assert over_ful.status_code == 400

    # Valid fulfillment
    valid_ful = client.post("/api/resources/fulfill-request", json={
        "request_id": req1["id"],
        "fulfilled_quantity": 5,
    })
    assert valid_ful.status_code == 200
    assert valid_ful.json()["request"]["status"] == "FULFILLED"

    # Audit log check: ensures entries exist with required provenance fields
    audit_res = client.get("/api/resources/audit-log")
    assert audit_res.status_code == 200
    entries = audit_res.json()["audit_trail"]
    assert len(entries) >= 3
    for entry in entries:
        assert "timestamp" in entry
        assert "action" in entry
        assert "request_id" in entry


# ---------------------------------------------------------------------------
# 2. Scenario Comparison & Severe vs Baseline Risk Invariants
# ---------------------------------------------------------------------------

def test_scenario_comparison_and_monotonicity():
    """
    Validates that:
    1. Severe flood scenario has higher critical risk count than Baseline.
    2. Comparison table is well-formed and non-empty.
    """
    comp_res = client.post("/api/scenarios/compare", json={})
    assert comp_res.status_code == 200
    data = comp_res.json()
    assert "comparison_table" in data
    assert "scenarios" in data

    scenarios = {s["scenario_id"]: s["metrics"] for s in data["scenarios"]}
    assert "baseline" in scenarios
    assert "severe" in scenarios

    base_crit = scenarios["baseline"]["critical_zones_count"]
    severe_crit = scenarios["severe"]["critical_zones_count"]
    assert severe_crit >= base_crit, "Severe scenario must have >= critical zones than baseline"

    # Activate scenario
    act_res = client.post("/api/scenarios/activate", json={"scenario_id": "moderate"})
    assert act_res.status_code == 200
    assert act_res.json()["status"] == "ACTIVATED"


# ---------------------------------------------------------------------------
# 3. Optimization Experiments & File Security Invariants
# ---------------------------------------------------------------------------

def test_experiments_execution_and_path_traversal_defense():
    """
    Validates running experiment suites and guards against directory traversal.
    """
    # 1. Generate a temporary risk map first
    risk_res = client.post("/api/risk/generate", json={
        "water_level_m": 8.0,
        "inflow_ktcmd": 600.0,
        "rainfall_mm_24h": 40.0,
    })
    assert risk_res.status_code == 200
    aid = risk_res.json()["analysis_id"]

    # 2. Run experiments
    exp_res = client.post("/api/optimization/experiments/run", json={
        "analysis_id": aid,
        "resolution": "low",
        "configs": [
            {
                "label": "Test-Config",
                "num_sensors": 4,
                "coverage_radius_km": 2.5,
                "comm_range_km": 4.0,
                "max_comm_nodes": 2,
            }
        ]
    })
    assert exp_res.status_code == 200
    exp_data = exp_res.json()
    assert len(exp_data["experiments"]) == 1
    exp0 = exp_data["experiments"][0]
    assert exp0["approach_a_greedy"]["objective_score"] >= exp0["approach_b_naive_topk"]["objective_score"]

    saved_file = exp_data["saved_to"]

    # 3. Fetch valid experiment results
    fetch_res = client.get(f"/api/optimization/experiments/results/{saved_file}")
    assert fetch_res.status_code == 200
    assert fetch_res.json()["experiments"][0]["config"]["num_sensors"] == 4

    # 4. Path traversal defense
    bad_res = client.get("/api/optimization/experiments/results/..%2F..%2Fetc%2Fpasswd")
    assert bad_res.status_code in (400, 404)


# ---------------------------------------------------------------------------
# 4. Forecasting Domain Invariants & Physical Bounds
# ---------------------------------------------------------------------------

def test_forecasting_domain_bounds_and_error_handling():
    """
    Validates that:
    1. Predictions fall within physically plausible water levels (5m to 25m).
    2. Requesting forecast on custom areas without gauge telemetry returns HTTP 400.
    """
    # Valid default benchmark prediction
    pred_res = client.post("/api/forecast/predict", json={"horizon_days": 1})
    assert pred_res.status_code == 200
    data = pred_res.json()
    predicted_stage = data["predicted_water_level_m"]
    assert 5.0 <= predicted_stage <= 25.0, f"Unphysical predicted stage: {predicted_stage}m"

    # Select custom area
    sel_res = client.post("/api/area/select", json={"location_query": "Tokyo, Japan"})
    if sel_res.status_code == 200:
        bad_fore = client.post("/api/forecast/predict", json={"horizon_days": 1})
        assert bad_fore.status_code == 400
        assert "hydro" in bad_fore.json()["detail"].lower() or "data" in bad_fore.json()["detail"].lower()
        # Reset back to default benchmark
        client.post("/api/area/reset")


# ---------------------------------------------------------------------------
# 5. Evacuation Routing & Geographic Geometry Invariants
# ---------------------------------------------------------------------------

def test_evacuation_routing_geometry_invariants():
    """
    Validates that evacuation routing:
    1. Returns non-empty path coordinates.
    2. Coordinates stay within valid lat/lon ranges.
    3. Path distance is strictly positive.
    """
    route_res = client.post("/api/evacuation/route", json={
        "origin_lat": 16.505,
        "origin_lon": 80.610,
        "dest_lat": 16.530,
        "dest_lon": 80.640,
        "risk_penalty_beta": 3.0,
    })
    assert route_res.status_code == 200
    data = route_res.json()
    assert data.get("status") == "SUCCESS"

    primary = data.get("primary_route", {})
    assert primary.get("total_distance_km", 0) > 0.0

    path_coords = primary.get("coordinates", [])
    assert len(path_coords) >= 2, "Path must contain at least start and end points"
    for pt in path_coords:
        lon, lat = pt[0], pt[1]
        assert 16.0 <= lat <= 17.0, f"Latitude out of basin bounds: {lat}"
        assert 80.0 <= lon <= 81.5, f"Longitude out of basin bounds: {lon}"


# ---------------------------------------------------------------------------
# 6. Session Isolation & Multi-User State Independence
# ---------------------------------------------------------------------------

def test_request_scoped_session_isolation():
    """
    Verifies that distinct analysis_ids maintain independent state
    and do not overwrite each other.
    """
    # Session A: High water level (Severe)
    res_a = client.post("/api/risk/generate", json={
        "water_level_m": 14.0,
        "inflow_ktcmd": 1200.0,
        "rainfall_mm_24h": 120.0,
    })
    assert res_a.status_code == 200
    aid_a = res_a.json()["analysis_id"]

    # Session B: Low water level (Dry)
    res_b = client.post("/api/risk/generate", json={
        "water_level_m": 6.5,
        "inflow_ktcmd": 200.0,
        "rainfall_mm_24h": 5.0,
    })
    assert res_b.status_code == 200
    aid_b = res_b.json()["analysis_id"]
    assert aid_a != aid_b

    # Fetch zones for Session A
    zones_a = client.get(f"/api/risk/zones?analysis_id={aid_a}").json()["zones"]
    # Fetch zones for Session B
    zones_b = client.get(f"/api/risk/zones?analysis_id={aid_b}").json()["zones"]

    crit_a = sum(1 for z in zones_a if z["risk_level"] == "CRITICAL")
    crit_b = sum(1 for z in zones_b if z["risk_level"] == "CRITICAL")
    assert crit_a > crit_b, f"Session A (severe) must have more critical zones than Session B (dry). Got {crit_a} vs {crit_b}"


# ---------------------------------------------------------------------------
# 7. Input Validation & Error Responses
# ---------------------------------------------------------------------------

def test_input_validation_boundary_rejection():
    """
    Ensures invalid parameters trigger HTTP 422 Unprocessable Content
    or HTTP 400 Bad Request.
    """
    # Negative sensor budget
    bad_opt = client.post("/api/optimization/run", json={"num_sensors": -5})
    assert bad_opt.status_code in (400, 422)

    # Invalid latitude (> 90)
    bad_evac = client.post("/api/evacuation/route", json={
        "origin_lat": 150.0,
        "origin_lon": 80.0,
        "dest_lat": 16.5,
        "dest_lon": 80.6,
    })
    assert bad_evac.status_code in (400, 422)

    # Negative QAOA circuit depth
    bad_qaoa = client.post("/api/optimization/quantum", json={
        "p": -1,
        "shots": 100,
    })
    assert bad_qaoa.status_code in (400, 422)
