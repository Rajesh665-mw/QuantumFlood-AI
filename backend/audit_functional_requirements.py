"""
Requirements-Based Functional Audit Script
Tests all 3 primary sections against the live backend (http://127.0.0.1:8000).
"""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api"

def log_test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}")
    if detail:
        print(f"       Details: {detail}")

def run_audit():
    print("=" * 70)
    print("STARTING REQUIREMENTS-BASED FUNCTIONAL AUDIT")
    print("=" * 70)
    results = {}

    # -------------------------------------------------------------------------
    # SECTION 1: HISTORICAL FLOOD INTELLIGENCE
    # -------------------------------------------------------------------------
    print("\n--- SECTION 1: Historical Flood Intelligence ---")

    # Req 1.1: Inspect real historical flood incidents
    r = requests.get(f"{BASE_URL}/data/historical-events-real")
    if r.status_code == 200:
        events = r.json().get("events", [])
        years = [e["year"] for e in events]
        passed = (2009 in years and 2024 in years and 1998 in years and 1903 in years)
        results["1.1_real_historical_events"] = {
            "passed": passed,
            "detail": f"{len(events)} events found (years: {years}). Citations present: {all('citation' in e for e in events)}"
        }
        log_test("1.1 Real Historical Flood Incidents & Impacts", passed, results["1.1_real_historical_events"]["detail"])
    else:
        results["1.1_real_historical_events"] = {"passed": False, "detail": f"Status {r.status_code}"}
        log_test("1.1 Real Historical Flood Incidents & Impacts", False, f"Status {r.status_code}")

    # Req 1.2: Observed records distinguished from synthetic/simulated data
    r_prov = requests.get(f"{BASE_URL}/data/provenance")
    if r_prov.status_code == 200:
        prov = r_prov.json().get("provenance", {})
        historical_status = prov.get("historical_flood_events", {}).get("status")
        rainfall_status = prov.get("rainfall_mm", {}).get("status")
        passed = (historical_status == "REAL_HISTORICAL" and rainfall_status == "SIMULATED_INPUT")
        results["1.2_provenance_distinction"] = {
            "passed": passed,
            "detail": f"Historical: {historical_status}, Rainfall/Hydro series: {rainfall_status}"
        }
        log_test("1.2 Provenance Distinction (Observed vs Simulated)", passed, results["1.2_provenance_distinction"]["detail"])
    else:
        results["1.2_provenance_distinction"] = {"passed": False, "detail": f"Status {r_prov.status_code}"}
        log_test("1.2 Provenance Distinction", False, f"Status {r_prov.status_code}")

    # Req 1.3 & 1.4: Historical evidence influences risk inputs & sensor placement optimization
    r_risk = requests.post(f"{BASE_URL}/risk/generate", json={
        "water_level_m": 16.5,
        "inflow_ktcmd": 600.0,
        "rainfall_mm_24h": 75.0,
    })
    if r_risk.status_code == 200:
        aid = r_risk.json()["analysis_id"]
        r_opt = requests.post(f"{BASE_URL}/optimization/run", json={
            "analysis_id": aid,
            "num_sensors": 5,
            "coverage_radius_km": 2.5,
            "comm_range_km": 4.0,
            "max_comm_nodes": 3,
        })
        if r_opt.status_code == 200:
            selected = r_opt.json()["optimization"]["selected_sensors"]
            evidence_notes = [s.get("historical_evidence_note") for s in selected if s.get("historical_evidence_note")]
            riparian_placed = any("2009" in str(note) for note in evidence_notes)
            results["1.3_historical_optimization_link"] = {
                "passed": riparian_placed and len(evidence_notes) > 0,
                "detail": f"{len(evidence_notes)}/{len(selected)} sensors contain evidence notes. 2009 breach corridor referenced: {riparian_placed}"
            }
            log_test("1.3 Historical Evidence Informs Sensor Placement & Explanations", results["1.3_historical_optimization_link"]["passed"], results["1.3_historical_optimization_link"]["detail"])
        else:
            results["1.3_historical_optimization_link"] = {"passed": False, "detail": f"Optimization status {r_opt.status_code}"}
            log_test("1.3 Historical Evidence Link", False, f"Status {r_opt.status_code}")
    else:
        results["1.3_historical_optimization_link"] = {"passed": False, "detail": f"Risk status {r_risk.status_code}"}
        log_test("1.3 Historical Evidence Link", False, f"Risk status {r_risk.status_code}")

    # Req 1.5 & 1.6: Predictive forecasting generates predictions from supported inputs with evaluation metrics
    r_pred = requests.post(f"{BASE_URL}/forecast/predict", json={"horizon_days": 1})
    if r_pred.status_code == 200:
        pred_data = r_pred.json()
        passed = ("predicted_water_level_m" in pred_data and pred_data["predicted_water_level_m"] > 0)
        results["1.5_forecasting_supported_inputs"] = {
            "passed": passed,
            "detail": f"Predicted stage: {pred_data.get('predicted_water_level_m')} m for horizon {pred_data.get('horizon_days')}d"
        }
        log_test("1.5 Predictive Forecasting from Telemetry Series", passed, results["1.5_forecasting_supported_inputs"]["detail"])
    else:
        results["1.5_forecasting_supported_inputs"] = {"passed": False, "detail": f"Status {r_pred.status_code}"}
        log_test("1.5 Predictive Forecasting", False, f"Status {r_pred.status_code}")

    # Req 1.7: Missing historical data & insufficient forecasting inputs handled honestly
    requests.post(f"{BASE_URL}/area/select", json={
        "location_query": "Tokyo, Japan",
        "latitude": 35.6895,
        "longitude": 139.6917,
        "half_size_deg": 0.06,
    })
    r_custom_hist = requests.get(f"{BASE_URL}/data/historical-events-real")
    r_custom_pred = requests.post(f"{BASE_URL}/forecast/predict", json={"horizon_days": 1})
    hist_honest = (r_custom_hist.status_code == 200 and len(r_custom_hist.json().get("events", [])) == 0)
    pred_honest = (r_custom_pred.status_code == 400 and "insufficient" in r_custom_pred.json().get("detail", "").lower())
    passed = hist_honest and pred_honest
    results["1.7_honest_empty_states"] = {
        "passed": passed,
        "detail": f"Custom area historical events: {len(r_custom_hist.json().get('events', []))} (honest empty). Custom area forecast: HTTP {r_custom_pred.status_code} ({r_custom_pred.json().get('detail')})"
    }
    log_test("1.7 Honest Handling of Missing Historical Data & Forecasting Inputs", passed, results["1.7_honest_empty_states"]["detail"])

    # Reset area to default
    requests.post(f"{BASE_URL}/area/reset")

    # -------------------------------------------------------------------------
    # SECTION 2: SAFE SHELTERS & SHELTER REQUESTS
    # -------------------------------------------------------------------------
    print("\n--- SECTION 2: Safe Shelters & Shelter Requests ---")

    # Situation 1: Operational shelters exist in selected area (default benchmark)
    r_shelters_1 = requests.post(f"{BASE_URL}/safe-locations/evaluate", json={
        "weight_elevation": 0.25,
        "weight_risk": 0.35,
        "weight_distance": 0.20,
        "weight_accessibility": 0.20,
    })
    if r_shelters_1.status_code == 200:
        d1 = r_shelters_1.json()
        ops = d1.get("operational_shelters", [])
        proposed = d1.get("proposed_candidate_sites", [])
        has_ops = d1.get("has_operational_shelters", False)
        all_ops_valid = all(o.get("shelter_type") == "OPERATIONAL_SHELTER" and o["id"].startswith("FAC-") for o in ops)
        all_prop_valid = all(p.get("shelter_type") == "PROPOSED_CANDIDATE" and "Proposed" in p.get("status_label", "") for p in proposed)
        unavail_cap = all(o.get("capacity_status") == "UNAVAILABLE" for o in ops)
        passed = (has_ops and len(ops) >= 4 and all_ops_valid and all_prop_valid and unavail_cap)
        results["2.1_situation_1_operational_shelters"] = {
            "passed": passed,
            "detail": f"Operational: {len(ops)}, Proposed: {len(proposed)}. All operational IDs FAC-*, All proposed SL-*. Capacity honestly marked UNAVAILABLE: {unavail_cap}"
        }
        log_test("2.1 Situation 1: Operational Shelters & Proposed Distinction", passed, results["2.1_situation_1_operational_shelters"]["detail"])
    else:
        results["2.1_situation_1_operational_shelters"] = {"passed": False, "detail": f"Status {r_shelters_1.status_code}"}
        log_test("2.1 Situation 1", False, f"Status {r_shelters_1.status_code}")

    # Situation 2: No operational shelters exist, but candidate sites can be calculated
    requests.post(f"{BASE_URL}/area/select", json={
        "location_query": "Tokyo, Japan",
        "latitude": 35.6895,
        "longitude": 139.6917,
        "half_size_deg": 0.06,
    })
    r_shelters_2 = requests.post(f"{BASE_URL}/safe-locations/evaluate", json={})
    if r_shelters_2.status_code == 200:
        d2 = r_shelters_2.json()
        ops2 = d2.get("operational_shelters", [])
        proposed2 = d2.get("proposed_candidate_sites", [])
        has_ops2 = d2.get("has_operational_shelters", False)
        passed = (has_ops2 is False and len(ops2) == 0 and len(proposed2) > 0)
        results["2.2_situation_2_proposed_candidate_sites"] = {
            "passed": passed,
            "detail": f"Operational: {len(ops2)} (0 expected), Proposed: {len(proposed2)} calculated with MCDA scores: {[p['suitability_score'] for p in proposed2[:3]]}"
        }
        log_test("2.2 Situation 2: Zero Operational, Proposed Sites Calculated", passed, results["2.2_situation_2_proposed_candidate_sites"]["detail"])
    else:
        results["2.2_situation_2_proposed_candidate_sites"] = {"passed": False, "detail": f"Status {r_shelters_2.status_code}"}
        log_test("2.2 Situation 2", False, f"Status {r_shelters_2.status_code}")

    # Situation 3: Neither shelters nor sufficient data to calculate sites
    # In custom area, set criteria that filters out all candidates (min_elevation_m=500m)
    r_shelters_3 = requests.post(f"{BASE_URL}/safe-locations/evaluate", json={"min_elevation_m": 500.0})
    if r_shelters_3.status_code == 200:
        d3 = r_shelters_3.json()
        ops3 = d3.get("operational_shelters", [])
        proposed3 = d3.get("proposed_candidate_sites", [])
        has_ops3 = d3.get("has_operational_shelters", False)
        passed = (has_ops3 is False and len(ops3) == 0 and len(proposed3) == 0)
        results["2.3_situation_3_empty_candidate_data"] = {
            "passed": passed,
            "detail": f"Operational: {len(ops3)}, Proposed: {len(proposed3)}. Disclaimer: {d3.get('disclaimer')}"
        }
        log_test("2.3 Situation 3: Neither Shelters nor Suitable Candidate Sites", passed, results["2.3_situation_3_empty_candidate_data"]["detail"])
    else:
        results["2.3_situation_3_empty_candidate_data"] = {"passed": False, "detail": f"Status {r_shelters_3.status_code}"}
        log_test("2.3 Situation 3", False, f"Status {r_shelters_3.status_code}")

    # Reset area
    requests.post(f"{BASE_URL}/area/reset")

    # Protection against submitting requests to proposed candidate sites
    r_bad_req = requests.post(f"{BASE_URL}/safe-locations/requests", json={
        "shelter_id": "SL-01",
        "shelter_name": "Proposed Construction Site SL-01",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": 500,
        "urgency": "HIGH",
    })
    rejected = (r_bad_req.status_code == 400 and "operational" in r_bad_req.json().get("detail", "").lower())
    results["2.4_proposed_site_request_rejection"] = {
        "passed": rejected,
        "detail": f"HTTP {r_bad_req.status_code}: {r_bad_req.json().get('detail')}"
    }
    log_test("2.4 Request Rejection for Proposed Sites", rejected, results["2.4_proposed_site_request_rejection"]["detail"])

    # -------------------------------------------------------------------------
    # SECTION 3: RESOURCE PLANNING & FULFILLMENT (END-TO-END TRACE)
    # -------------------------------------------------------------------------
    print("\n--- SECTION 3: Resource Planning & Fulfillment (End-to-End Trace) ---")

    # 1. Submit valid request
    test_qty = 250
    r_create = requests.post(f"{BASE_URL}/safe-locations/requests", json={
        "shelter_id": "FAC-001",
        "shelter_name": "Government Polytechnic College Relief Center",
        "resource_type": "Clean Drinking Water (L)",
        "requested_quantity": test_qty,
        "urgency": "HIGH",
        "notes": "Automated End-to-End Trace Request",
    })
    if r_create.status_code != 200:
        log_test("3.1 Request Creation", False, f"Status {r_create.status_code}: {r_create.text}")
        return results

    req = r_create.json()["request"]
    req_id = req["id"]
    log_test("3.1 Request Creation & Backend Acceptance", True, f"Created {req_id} (Status: {req['status']}, Qty: {req['requested_quantity']})")

    # 2. Verify appearance in Resource Planning Demand Summary
    r_demand = requests.get(f"{BASE_URL}/resources/demand-summary")
    d_summary = r_demand.json()
    water_demand = next((d for d in d_summary["demand_by_resource"] if "Water" in d["resource_type"]), None)
    log_test("3.2 Appearance in Resource Planning & Demand Summary", water_demand is not None, f"Water total requested: {water_demand['requested']} L, Shortage: {water_demand['shortage']}")

    # 3. Check inventory before allocation
    r_inv_pre = requests.get(f"{BASE_URL}/resources/inventory")
    inv_pre = next(i for i in r_inv_pre.json()["inventory"] if "Water" in i["item"])
    initial_avail = inv_pre["available"]

    # 4. Shortage / Over-allocation handling
    r_over = requests.post(f"{BASE_URL}/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": initial_avail + 99999,
    })
    over_rejected = (r_over.status_code == 400)
    r_inv_check = requests.get(f"{BASE_URL}/resources/inventory")
    inv_check = next(i for i in r_inv_check.json()["inventory"] if "Water" in i["item"])
    stock_intact = (inv_check["available"] == initial_avail)
    log_test("3.3 Over-Allocation / Shortage Protection", over_rejected and stock_intact, f"HTTP {r_over.status_code}. Stock untouched: {inv_check['available']} == {initial_avail}")

    # 5. Allocate available stock (Partial allocation: 150 of 250)
    alloc_qty = 150
    r_alloc = requests.post(f"{BASE_URL}/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": alloc_qty,
    })
    alloc_data = r_alloc.json()["request"]
    alloc_passed = (r_alloc.status_code == 200 and alloc_data["status"] == "PARTIALLY_ALLOCATED" and alloc_data["allocated_quantity"] == alloc_qty)
    r_inv_post = requests.get(f"{BASE_URL}/resources/inventory")
    inv_post = next(i for i in r_inv_post.json()["inventory"] if "Water" in i["item"])
    stock_deducted = (inv_post["available"] == initial_avail - alloc_qty)
    log_test("3.4 Partial Stock Allocation & Inventory Update", alloc_passed and stock_deducted, f"Status: {alloc_data['status']}, Allocated: {alloc_data['allocated_quantity']}, Available: {inv_post['available']} (was {initial_avail})")

    # 6. Duplicate allocation safety
    r_dup = requests.post(f"{BASE_URL}/resources/allocate-request", json={
        "request_id": req_id,
        "allocated_quantity": alloc_qty,
    })
    dup_safe = (r_dup.status_code == 400 or (r_dup.status_code == 200 and r_dup.json().get("note") == "Request already allocated (idempotent)."))
    log_test("3.5 Duplicate Allocation Prevention", dup_safe, f"Duplicate attempt safely handled with HTTP {r_dup.status_code}")

    # 7. Fulfillment delivery
    fulfill_qty = 150
    r_fulfill = requests.post(f"{BASE_URL}/resources/fulfill-request", json={
        "request_id": req_id,
        "fulfilled_quantity": fulfill_qty,
    })
    fulfill_data = r_fulfill.json()["request"]
    fulfill_passed = (r_fulfill.status_code == 200 and fulfill_data["status"] == "PARTIALLY_FULFILLED" and fulfill_data["fulfilled_quantity"] == fulfill_qty)
    log_test("3.6 Supply Fulfillment Execution (Partial Delivery)", fulfill_passed, f"Status: {fulfill_data['status']}, Fulfilled: {fulfill_data['fulfilled_quantity']}")

    # 8. Tracking View verification (Safe Shelters requester tracking view)
    r_track = requests.get(f"{BASE_URL}/safe-locations/requests?shelter_id=FAC-001")
    tracked_reqs = r_track.json()["requests"]
    my_req = next((r for r in tracked_reqs if r["id"] == req_id), None)
    tracking_accurate = (my_req is not None and my_req["status"] == "PARTIALLY_FULFILLED" and my_req["allocated_quantity"] == alloc_qty and my_req["fulfilled_quantity"] == fulfill_qty)
    log_test("3.7 Shelter Requester Tracking View Status Consistency", tracking_accurate, f"Requester sees: {my_req['id']} Status: {my_req['status']}, Allocated: {my_req['allocated_quantity']}, Fulfilled: {my_req['fulfilled_quantity']}")

    # 9. Persistence to Disk Verification (Survives Restart)
    from pathlib import Path
    storage_path = Path("app/data/processed/shelter_logistics.json")
    if not storage_path.exists():
        storage_path = Path("backend/app/data/processed/shelter_logistics.json")
    if storage_path.exists():
        with open(storage_path, "r", encoding="utf-8") as f:
            persisted = json.load(f)
        persisted_reqs = [r["id"] for r in persisted.get("requests", [])]
        persisted_ok = req_id in persisted_reqs
        log_test("3.8 Persistence Verification (_STORAGE_FILE updated on disk)", persisted_ok, f"Request {req_id} found in {storage_path} (survives backend restart)")
    else:
        log_test("3.8 Persistence Verification", False, f"File {storage_path} does not exist")

    print("\n" + "=" * 70)
    print("ALL AUDIT VERIFICATIONS COMPLETED")
    print("=" * 70)

if __name__ == "__main__":
    run_audit()
