"""
Unit Tests for Module 5 — Emergency Resource Allocation
"""
import pytest
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.resource_allocation_service import allocate_emergency_resources


def test_resource_allocation_respects_budgets_and_caps():
    zones = get_risk_zone_geometry("default")
    for i, z in enumerate(zones):
        z["risk_score"] = 4 if i < 8 else (2 if i < 16 else 1)
        z["risk_level"] = "CRITICAL" if i < 8 else ("MODERATE" if i < 16 else "LOW")

    res = allocate_emergency_resources(
        zones=zones,
        rescue_teams=5,
        medical_teams=3,
        relief_units=4,
        emergency_vehicles=4,
        min_risk_level="MODERATE"
    )

    assert res["status"] == "SUCCESS"
    summary = res["summary"]
    alloc_q = summary["allocated_quantities"]

    assert alloc_q["rescue_teams"] <= 5
    assert alloc_q["medical_teams"] <= 3
    assert alloc_q["relief_units"] <= 4
    assert alloc_q["emergency_vehicles"] <= 4

    # No resources assigned to LOW risk zones
    for alloc in res["allocations"]:
        assert alloc["risk_level"] in ("CRITICAL", "MODERATE")
        assert alloc["total_units_allocated"] > 0
        assert "Zone" in alloc["explanation"]


def test_resource_allocation_zero_budget_edge_case():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 4
        z["risk_level"] = "CRITICAL"

    res = allocate_emergency_resources(
        zones=zones,
        rescue_teams=0,
        medical_teams=0,
        relief_units=0,
        emergency_vehicles=0
    )

    assert res["status"] == "SUCCESS"
    assert res["summary"]["zones_serviced_count"] == 0
    assert len(res["allocations"]) == 0
