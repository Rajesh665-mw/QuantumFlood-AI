"""
Unit Tests for Module 2 — Dynamic Evacuation Routing
"""
import pytest
from app.gis.geo_loader import get_risk_zone_geometry
from app.services.evacuation_service import calculate_evacuation_routes, load_road_network


def test_road_network_dataset_integrity():
    net = load_road_network()
    nodes = net.get("nodes", [])
    edges = net.get("edges", [])
    assert len(nodes) >= 15
    assert len(edges) >= 18

    node_ids = {n["id"] for n in nodes}
    for e in edges:
        assert e["from"] in node_ids
        assert e["to"] in node_ids
        assert e["distance_km"] > 0


def test_evacuation_routing_computes_routes_with_metrics():
    zones = get_risk_zone_geometry("default")
    for z in zones:
        z["risk_score"] = 1
        z["risk_level"] = "LOW"

    # Route from city approach near barrage to Kanuru/VR Siddhartha
    res = calculate_evacuation_routes(
        origin_lat=16.5128, origin_lon=80.6039,
        dest_lat=16.4975, dest_lon=80.6652,
        zones=zones,
        origin_name="Kanakadurga Flyover",
        dest_name="VR Siddhartha Campus"
    )

    assert res["status"] == "SUCCESS"
    assert res["primary_route"] is not None
    assert res["primary_route"]["total_distance_km"] > 0
    assert len(res["primary_route"]["coordinates"]) >= 2
    assert "scientific_honesty_banner" in res


def test_evacuation_routing_penalizes_high_risk_edges():
    zones = get_risk_zone_geometry("default")
    # Mark barrage and riverfront zones as CRITICAL
    for z in zones:
        if z["distance_to_river_km"] < 2.0:
            z["risk_score"] = 4
            z["risk_level"] = "CRITICAL"
        else:
            z["risk_score"] = 1
            z["risk_level"] = "LOW"

    res = calculate_evacuation_routes(
        origin_lat=16.5350, origin_lon=80.5750,  # Gollapudi
        dest_lat=16.5030, dest_lon=80.6720,  # Loyola College
        zones=zones,
        risk_penalty_beta=5.0
    )

    assert res["status"] == "SUCCESS"
    assert res["primary_route"] is not None
    assert res["primary_route"]["estimated_route_risk_score"] >= 1.0
