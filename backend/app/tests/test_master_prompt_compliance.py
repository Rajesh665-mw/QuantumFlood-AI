import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import json

from app.main import app
from app.services.active_area import clear_active_area, set_active_area

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_area():
    """Ensure area is reset to default benchmark before and after each test."""
    clear_active_area()
    yield
    clear_active_area()


# =====================================================================
# 1. HISTORICAL FLOOD INTELLIGENCE TESTS
# =====================================================================

def test_historical_events_benchmark_corridor():
    """Default Vijayawada benchmark area returns verified historical flood records."""
    clear_active_area()
    res = client.get("/api/data/historical-events-real")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    events = data["events"]
    assert len(events) >= 4

    years = [e["year"] for e in events]
    assert 1903 in years
    assert 1998 in years
    assert 2009 in years
    assert 2024 in years

    # Verify sources and transparent severity calculations
    for e in events:
        assert "citation" in e and len(e["citation"]) > 5
        assert e["data_source"] == "REAL_HISTORICAL"
        assert "severity_class" in e
        assert "severity_calculation_method" in e

    # 2009 landmark flood should be classified as catastrophic
    evt_2009 = next(e for e in events if e["year"] == 2009)
    assert evt_2009["severity_class"] == "CATASTROPHIC"
    assert evt_2009["peak_discharge_cusecs"] == 1143000.0
    assert "Z-001" in evt_2009["inundated_risk_zones"]


def test_historical_events_custom_area_honest_empty():
    """Custom geocoded area with no archives returns honest empty state."""
    custom_area = {
        "name": "Custom Study Area",
        "bounding_box": {"min_lat": 17.3, "max_lat": 17.5, "min_lon": 78.4, "max_lon": 78.6},
        "is_default_location": False,
    }
    set_active_area(custom_area)

    res = client.get("/api/data/historical-events-real")
    assert res.status_code == 200
    data = res.json()
    assert data["events"] == []
    assert data["data_provenance"] == "UNAVAILABLE"
    assert "No historical flood event records available" in data["note"]


def test_historical_evidence_linked_to_sensor_placement():
    """Optimizer links historical flood evidence to placed sensor reasoning."""
    clear_active_area()
    risk_res = client.post("/api/risk/generate", json={
        "water_level_m": 16.5,
        "inflow_ktcmd": 600.0,
        "rainfall_mm_24h": 75.0,
    })
    assert risk_res.status_code == 200
    aid = risk_res.json()["analysis_id"]

    res = client.post("/api/optimization/run", json={
        "analysis_id": aid,
        "num_sensors": 5,
        "coverage_radius_km": 2.5,
        "comm_range_km": 4.0,
        "max_comm_nodes": 3,
    })
    assert res.status_code == 200
    data = res.json()
    selected = data["optimization"]["selected_sensors"]
    assert len(selected) > 0

    # Placed sensors must carry historical_evidence_note
    has_riparian_sensor = False
    for s in selected:
        assert "historical_evidence_note" in s
        if s.get("near_river"):
            has_riparian_sensor = True
            assert "2009" in s["historical_evidence_note"]
            assert "corridor" in s["historical_evidence_note"].lower()
    assert has_riparian_sensor, "At least one sensor should be placed in near-river riparian zones"


def test_forecast_sufficient_data_benchmark():
    """Forecast generates valid prediction on default area with hydro series."""
    clear_active_area()
    res = client.post("/api/forecast/predict", json={"horizon_days": 1})
    assert res.status_code == 200
    pred = res.json()
    assert "predicted_water_level_m" in pred
    assert pred["predicted_water_level_m"] > 0
    assert pred["horizon_days"] == 1


def test_forecast_insufficient_data_rejection():
    """Forecast requests for custom areas with insufficient telemetry are rejected with 400."""
    custom_area = {
        "name": "Custom Region",
        "bounding_box": {"min_lat": 13.0, "max_lat": 13.2, "min_lon": 80.1, "max_lon": 80.3},
        "is_default_location": False,
    }
    set_active_area(custom_area)

    pred_res = client.post("/api/forecast/predict", json={"horizon_days": 1})
    assert pred_res.status_code == 400
    assert "Insufficient hydrological data" in pred_res.json()["detail"]

    train_res = client.post("/api/forecast/train", json={"horizon_days": 1})
    assert train_res.status_code == 400
    assert "Insufficient hydrological data" in train_res.json()["detail"]

    compare_res = client.post("/api/forecast/compare", json={"horizon_days": 1})
    assert compare_res.status_code == 400
    assert "Insufficient hydrological data" in compare_res.json()["detail"]


# =====================================================================
# 2. SAFE SHELTERS & SHELTER REQUESTS TESTS
# =====================================================================

def test_operational_shelters_distinguished_from_proposed():
    """Operational shelters and proposed candidate sites are strictly distinguished."""
    clear_active_area()
    res = client.post("/api/safe-locations/evaluate", json={
        "weight_elevation": 0.25,
        "weight_risk": 0.35,
        "weight_distance": 0.20,
        "weight_accessibility": 0.20,
    })
    assert res.status_code == 200
    data = res.json()

    assert data["has_operational_shelters"] is True
    ops = data["operational_shelters"]
    assert len(ops) >= 4
    for o in ops:
        assert o["shelter_type"] == "OPERATIONAL_SHELTER"
        assert o["id"].startswith("FAC-")

    proposed = data["proposed_candidate_sites"]
    assert len(proposed) >= 1
    for p in proposed:
        assert p["shelter_type"] == "PROPOSED_CANDIDATE"
        assert "Proposed Shelter Site" in p["status_label"]
        assert p["id"].startswith("SL-")


def test_custom_area_has_no_operational_shelters_only_proposed():
    """Custom area returns 0 operational shelters and recommends proposed candidate sites."""
    custom_area = {
        "name": "Custom Valley",
        "bounding_box": {"min_lat": 18.0, "max_lat": 18.2, "min_lon": 83.0, "max_lon": 83.2},
        "is_default_location": False,
    }
    set_active_area(custom_area)

    res = client.post("/api/safe-locations/evaluate", json={
        "weight_elevation": 0.25,
        "weight_risk": 0.35,
        "weight_distance": 0.20,
        "weight_accessibility": 0.20,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["has_operational_shelters"] is False
    assert len(data["operational_shelters"]) == 0
    assert len(data["proposed_candidate_sites"]) > 0


def test_shelter_request_rejected_for_proposed_candidate_site():
    """Shelter requests cannot be submitted for proposed candidate sites (SL-*)."""
    clear_active_area()
    bad_req = {
        "shelter_id": "SL-01",
        "shelter_name": "Proposed Construction Site",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": 500,
        "urgency": "HIGH",
    }
    res = client.post("/api/safe-locations/requests", json=bad_req)
    assert res.status_code == 400
    detail = res.json()["detail"]
    assert "proposed shelter candidate sites" in detail.lower() or "operational" in detail.lower()


def test_shelter_request_rejected_when_no_operational_shelters():
    """In custom area with no operational shelters, all request submissions are rejected."""
    custom_area = {
        "name": "Custom Basin",
        "bounding_box": {"min_lat": 19.0, "max_lat": 19.2, "min_lon": 84.0, "max_lon": 84.2},
        "is_default_location": False,
    }
    set_active_area(custom_area)

    req = {
        "shelter_id": "FAC-001",
        "shelter_name": "Nonexistent in this area",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": 500,
        "urgency": "HIGH",
    }
    res = client.post("/api/safe-locations/requests", json=req)
    assert res.status_code == 400


# =====================================================================
# 3. RESOURCE PLANNING & FULFILLMENT TESTS
# =====================================================================

def test_resource_request_allocation_and_fulfillment_workflow():
    """Full end-to-end test of request lodging, inventory validation, allocation, and fulfillment."""
    clear_active_area()

    # 1. Submit request for operational shelter FAC-001
    submit_res = client.post("/api/safe-locations/requests", json={
        "shelter_id": "FAC-001",
        "shelter_name": "Government Polytechnic College Relief Center",
        "resource_type": "Emergency Food Rations (Packs)",
        "requested_quantity": 150,
        "urgency": "CRITICAL",
        "notes": "Urgent evacuee replenishment",
    })
    assert submit_res.status_code == 200
    req = submit_res.json()["request"]
    req_id = req["id"]
    assert req["status"] == "PENDING"
    assert req["allocated_quantity"] == 0
    assert req["fulfilled_quantity"] == 0

    # 2. Verify visible in Resource Planning demand summary
    demand_res = client.get("/api/resources/demand-summary")
    assert demand_res.status_code == 200
    demand = demand_res.json()
    food_demand = next((d for d in demand["demand_by_resource"] if "Food" in d["resource_type"]), None)
    assert food_demand is not None
    assert food_demand["requested"] >= 150

    # 3. Check inventory before allocation
    inv_res = client.get("/api/resources/inventory")
    assert inv_res.status_code == 200
    inv = inv_res.json()["inventory"]
    food_inv = next(i for i in inv if "Food" in i["item"])
    initial_available = food_inv["available"]

    # 4. Attempt over-allocation (must fail without reducing inventory)
    over_res = client.post("/api/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": initial_available + 50000,
    })
    assert over_res.status_code == 400

    inv_after_over = client.get("/api/resources/inventory").json()["inventory"]
    food_inv_after_over = next(i for i in inv_after_over if "Food" in i["item"])
    assert food_inv_after_over["available"] == initial_available, "Failed allocation must not reduce stock"

    # 5. Valid allocation of 100 units (partial fulfillment)
    alloc_res = client.post("/api/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": 100,
    })
    assert alloc_res.status_code == 200
    alloc_data = alloc_res.json()["request"]
    assert alloc_data["status"] == "PARTIALLY_ALLOCATED"
    assert alloc_data["allocated_quantity"] == 100

    # Stock should be decremented by exactly 100
    inv_after_alloc = client.get("/api/resources/inventory").json()["inventory"]
    food_inv_after_alloc = next(i for i in inv_after_alloc if "Food" in i["item"])
    assert food_inv_after_alloc["available"] == initial_available - 100

    # 6. Duplicate allocation protection
    dup_alloc = client.post("/api/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": 50,
    })
    assert dup_alloc.status_code == 400
    assert "already been allocated" in dup_alloc.json()["detail"].lower() or "re-allocation" in dup_alloc.json()["detail"].lower()

    # 7. Fulfillment (partial fulfillment matches requested quantity vs allocated)
    fulfill_res = client.post("/api/resources/fulfill-request", json={
        "request_id": req_id,
        "fulfilled_quantity": 100,
    })
    assert fulfill_res.status_code == 200
    fulfilled_data = fulfill_res.json()["request"]
    assert fulfilled_data["status"] == "PARTIALLY_FULFILLED"
    assert fulfilled_data["fulfilled_quantity"] == 100

    # 8. Cannot re-fulfill or over-fulfill completed request
    re_fulfill = client.post("/api/resources/fulfill-request", json={
        "request_id": req_id,
        "fulfilled_quantity": 10,
    })
    assert re_fulfill.status_code == 400

    # 9. Audit trail verification
    audit_res = client.get("/api/resources/audit-log")
    assert audit_res.status_code == 200
    trail = audit_res.json()["audit_trail"]
    actions = [t["action"] for t in trail if t.get("request_id") == req_id]
    assert "ALLOCATE_INVENTORY" in actions
    assert "DELIVERY_FULFILLMENT" in actions

    # 10. Persistence verification: shelter_logistics.json exists and contains this request
    logistics_file = Path(__file__).resolve().parents[2] / "app" / "data" / "processed" / "shelter_logistics.json"
    assert logistics_file.exists()
    with open(logistics_file, "r") as f:
        persisted = json.load(f)
    req_ids = [r["id"] for r in persisted.get("requests", [])]
    assert req_id in req_ids
