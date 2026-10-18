from fastapi.testclient import TestClient
from app.main import app
from app.services.shelter_request_service import reset_shelter_logistics

client = TestClient(app)


def test_shelter_requests_flow():
    reset_shelter_logistics()
    # 1. List requests
    res = client.get("/api/safe-locations/requests")
    assert res.status_code == 200
    data = res.json()
    assert "requests" in data
    initial_count = len(data["requests"])
    assert initial_count >= 1

    # 2. Create a request
    new_req = {
        "shelter_id": "FAC-TEST",
        "shelter_name": "Test Relief Center",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": 500,
        "urgency": "HIGH",
        "notes": "Emergency test request"
    }
    create_res = client.post("/api/safe-locations/requests", json=new_req)
    assert create_res.status_code == 200
    created_data = create_res.json()
    assert created_data["status"] == "SUCCESS"
    req_id = created_data["request"]["id"]
    assert created_data["request"]["shelter_id"] == "FAC-TEST"
    assert created_data["request"]["status"] == "PENDING"

    # 3. List with filter
    filter_res = client.get(f"/api/safe-locations/requests?shelter_id=FAC-TEST")
    assert filter_res.status_code == 200
    filtered = filter_res.json()["requests"]
    assert len(filtered) == 1
    assert filtered[0]["id"] == req_id


def test_inventory_and_demand_summary():
    # Inventory
    inv_res = client.get("/api/resources/inventory")
    assert inv_res.status_code == 200
    inv = inv_res.json()["inventory"]
    assert any(i["item"] == "Clean Drinking Water (L)" for i in inv)

    # Demand Summary
    dem_res = client.get("/api/resources/demand-summary")
    assert dem_res.status_code == 200
    demand = dem_res.json()
    assert "demand_by_resource" in demand
    assert "total_requests" in demand
    assert demand["total_requests"] >= 1


def test_allocation_and_fulfillment_rules():
    # Create a request to allocate
    new_req = {
        "shelter_id": "FAC-ALLOC-TEST",
        "shelter_name": "Allocation Test Center",
        "resource_type": "Medical First-Aid Kits",
        "requested_quantity": 20,
        "urgency": "CRITICAL"
    }
    c_res = client.post("/api/safe-locations/requests", json=new_req)
    req_id = c_res.json()["request"]["id"]

    # Over-allocation test (exceeding stock limit of 250)
    over_res = client.post("/api/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": 999999
    })
    assert over_res.status_code == 400
    assert "available in stock" in over_res.json()["detail"].lower()

    # Valid allocation
    valid_res = client.post("/api/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": 20
    })
    assert valid_res.status_code == 200
    alloc_data = valid_res.json()
    assert alloc_data["request"]["status"] == "ALLOCATED"
    assert alloc_data["request"]["allocated_quantity"] == 20

    # Over-fulfillment test (> allocated)
    over_fulfill = client.post("/api/resources/fulfill-request", json={
        "request_id": req_id,
        "fulfilled_quantity": 30
    })
    assert over_fulfill.status_code == 400

    # Valid fulfillment
    fulfill_res = client.post("/api/resources/fulfill-request", json={
        "request_id": req_id,
        "fulfilled_quantity": 20
    })
    assert fulfill_res.status_code == 200
    assert fulfill_res.json()["request"]["status"] == "FULFILLED"

    # Audit log check
    audit_res = client.get("/api/resources/audit-log")
    assert audit_res.status_code == 200
    actions = [e["action"] for e in audit_res.json()["audit_trail"]]
    assert "ALLOCATE_INVENTORY" in actions
    assert "DELIVERY_FULFILLMENT" in actions
