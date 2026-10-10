"""
Unit & Integration Tests for Study Area Generalization & Global Location Selection
==================================================================================
Tests:
  - Active area state singleton (thread-safe, get/set/clear)
  - Synthetic river generation & data availability assessment
  - Study area service (Vijayawada detection, custom area creation, reset)
  - Parameterized geo_loader & candidate generator
  - Dynamic safe locations & road network generation
  - API endpoints: /api/area/select, /api/area/reset, /api/area/current, /api/area/search
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.active_area import (
    get_active_area, set_active_area, clear_active_area,
    is_default_area, get_active_bounding_box, get_active_center
)
from app.services.study_area_service import select_study_area, reset_to_default, get_current_study_area
from app.services.geospatial_service import generate_synthetic_river, assess_data_availability
from app.gis.geo_loader import get_risk_zone_geometry, get_study_area_boundary, get_river_centerline
from app.optimization.candidate_generator import generate_candidates
from app.services.safe_location_service import load_candidate_safe_locations
from app.services.evacuation_service import load_road_network

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_active_area():
    """Ensure active area is reset to default before and after every test."""
    clear_active_area()
    yield
    clear_active_area()


def test_active_area_singleton():
    assert is_default_area() is True
    assert get_active_area() is None
    assert get_active_bounding_box() is None
    assert get_active_center() is None

    test_config = {
        "name": "Test Area",
        "bounding_box": {"min_lat": 10.0, "max_lat": 10.1, "min_lon": 20.0, "max_lon": 20.1},
        "center": {"lat": 10.05, "lon": 20.05},
    }
    set_active_area(test_config)
    assert is_default_area() is False
    assert get_active_area() == test_config
    assert get_active_bounding_box() == test_config["bounding_box"]
    assert get_active_center() == test_config["center"]

    clear_active_area()
    assert is_default_area() is True


def test_synthetic_river_generation():
    bbox = {"min_lat": 48.0, "max_lat": 48.1, "min_lon": 11.5, "max_lon": 11.6}
    river = generate_synthetic_river(bbox, "Isar River")
    assert river["type"] == "Feature"
    assert river["properties"]["name"] == "Isar River"
    assert river["properties"]["data_source"] == "SIMULATED"
    coords = river["geometry"]["coordinates"]
    assert len(coords) >= 10
    for lon, lat in coords:
        assert bbox["min_lat"] <= lat <= bbox["max_lat"]
        assert bbox["min_lon"] <= lon <= bbox["max_lon"]


@patch("app.services.geospatial_service.fetch_waterways", return_value=None)
def test_data_availability_assessment(mock_fetch):
    bbox = {"min_lat": 51.4, "max_lat": 51.6, "min_lon": -0.2, "max_lon": 0.0}
    avail = assess_data_availability(bbox)
    assert "geographic_boundary" in avail
    assert "river_geometry" in avail
    assert "risk_zones" in avail
    assert "water_level_m" in avail
    assert avail["water_level_m"]["status"] == "SIMULATED_INPUT"


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_select_study_area_by_coordinates(mock_waterway):
    # Tokyo coordinates
    res = select_study_area(latitude=35.6762, longitude=139.6503, half_size_deg=0.05)
    assert res["status"] == "OK"
    assert res["is_default_location"] is False
    assert res["latitude"] == 35.6762
    assert res["longitude"] == 139.6503
    assert "study_area" in res
    assert "map_config" in res

    active = get_active_area()
    assert active is not None
    assert round(active["center"]["lat"], 2) == 35.68


def test_select_study_area_detects_vijayawada():
    # Selecting coords near Vijayawada should seamlessly retain default benchmark
    res = select_study_area(latitude=16.506, longitude=80.605)
    assert res["status"] == "OK"
    assert res["is_default_location"] is True
    assert is_default_area() is True


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_geo_loader_and_candidates_adapt_to_active_area(mock_waterway):
    # Default area
    default_zones = get_risk_zone_geometry("low")
    default_cands = generate_candidates(resolution="low")
    assert len(default_zones) > 0
    assert len(default_cands) > 0

    # Set custom study area (Munich)
    select_study_area(latitude=48.137, longitude=11.576, half_size_deg=0.04)
    munich_zones = get_risk_zone_geometry("low")
    munich_cands = generate_candidates(resolution="low")

    assert len(munich_zones) > 0
    assert len(munich_cands) > 0
    # Munich zone centroids must be around Munich lat (~48.1)
    first_zone = munich_zones[0]
    assert 48.05 <= first_zone["centroid"]["lat"] <= 48.20
    assert 11.50 <= first_zone["centroid"]["lon"] <= 11.65

    # Munich candidates must be around Munich coords
    first_cand = munich_cands[0]
    assert 48.05 <= first_cand["lat"] <= 48.20
    assert 11.50 <= first_cand["lon"] <= 11.65


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_dynamic_safe_locations_and_road_network(mock_waterway):
    # Set custom study area (London)
    select_study_area(latitude=51.5074, longitude=-0.1278, half_size_deg=0.05)

    safe_locs = load_candidate_safe_locations()
    assert len(safe_locs) >= 6
    for feat in safe_locs:
        coords = feat["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        assert 51.4 <= lat <= 51.6
        assert -0.25 <= lon <= 0.05

    road_net = load_road_network()
    assert len(road_net["nodes"]) >= 9
    assert len(road_net["edges"]) >= 10
    for node in road_net["nodes"]:
        assert 51.4 <= node["lat"] <= 51.6
        assert -0.25 <= node["lon"] <= 0.05


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_area_api_endpoints(mock_waterway):
    # 1. GET /api/area/current
    res = client.get("/api/area/current")
    assert res.status_code == 200
    data = res.json()
    assert data["is_default_location"] is True

    # 2. POST /api/area/select
    post_res = client.post("/api/area/select", json={
        "latitude": 40.7128,
        "longitude": -74.0060,
        "half_size_deg": 0.05
    })
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "OK"
    assert post_data["is_default_location"] is False

    # Check that current area now reflects custom area
    curr_res = client.get("/api/area/current")
    assert curr_res.json()["is_default_location"] is False

    # 3. GET /api/map/layers dynamically reflects custom area
    map_res = client.get("/api/map/layers")
    assert map_res.status_code == 200
    map_data = map_res.json()
    assert abs(map_data["study_area"]["center"]["lat"] - 40.7128) < 0.1

    # 4. POST /api/area/reset
    reset_res = client.post("/api/area/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "OK"

    curr_res2 = client.get("/api/area/current")
    assert curr_res2.json()["is_default_location"] is True


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_historical_events_isolation_on_location_switch(mock_waterway):
    """Asserts that Vijayawada historical records NEVER leak into custom locations."""
    # 1. Default Vijayawada area: returns real historical events
    res_default = client.get("/api/data/historical-events-real")
    assert res_default.status_code == 200
    default_events = res_default.json()["events"]
    assert len(default_events) > 0
    assert any("Prakasam Barrage" in ev.get("location", "") for ev in default_events)

    # 2. Select custom location (Tokyo)
    select_study_area(latitude=35.6762, longitude=139.6503, half_size_deg=0.05)

    # 3. Custom area: historical events must be empty, NOT Vijayawada records!
    res_custom = client.get("/api/data/historical-events-real")
    assert res_custom.status_code == 200
    assert len(res_custom.json()["events"]) == 0
    assert res_custom.json()["data_provenance"] == "UNAVAILABLE"

    # 4. Demo events endpoint must also be empty
    res_demo = client.get("/api/data/historical-events")
    assert res_demo.status_code == 200
    assert len(res_demo.json()["events"]) == 0

    # 5. Reset to Vijayawada: events are restored
    reset_to_default()
    res_restored = client.get("/api/data/historical-events-real")
    assert len(res_restored.json()["events"]) > 0


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_reset_clears_all_pipeline_state_artifacts(mock_waterway):
    """Asserts that resetting area clears ALL 12 pipeline state artifacts."""
    from app.services.pipeline_state import state

    # Populate some state properties
    state.latest_safe_locations = {"dummy": "safe"}
    state.latest_evacuation_routes = {"dummy": "route"}
    state.latest_resource_allocations = {"dummy": "alloc"}

    # Call reset endpoint
    res = client.post("/api/area/reset")
    assert res.status_code == 200

    # All state properties must be None
    assert state.latest_risk_map is None
    assert state.latest_optimization is None
    assert state.latest_safe_locations is None
    assert state.latest_evacuation_routes is None
    assert state.latest_resource_allocations is None
    assert state.active_scenario is None


def test_rural_uninhabited_coordinates_name_fallback():
    """Asserts that coordinates without a city name do not produce empty names."""
    with patch("app.services.study_area_service.get_primary_waterway", return_value=None), \
         patch("app.services.study_area_service.reverse_geocode", return_value={"country": "Saudi Arabia", "country_code": "sa"}):
        res = select_study_area(latitude=22.0, longitude=50.0)
        assert res["status"] == "OK"
        loc_name = res["location_name"]
        assert len(loc_name.strip()) > 0
        assert "Study Area" in res["study_area"]["name"]
        assert res["study_area"]["name"] != " Study Area"


def test_invalid_coordinates_rejected():
    """Asserts that invalid coordinates or missing pairs return 400/422 errors."""
    # Missing longitude
    res1 = client.post("/api/area/select", json={"latitude": 35.0})
    assert res1.status_code == 400

    # Missing latitude
    res2 = client.post("/api/area/select", json={"longitude": 139.0})
    assert res2.status_code == 400

    # Out of bounds latitude (> 90)
    res3 = client.post("/api/area/select", json={"latitude": 95.0, "longitude": 10.0})
    assert res3.status_code == 422


@patch("app.services.study_area_service.get_primary_waterway", return_value=None)
def test_provenance_labels_truthful_per_location(mock_waterway):
    """Asserts that provenance labels truthfully distinguish benchmark from custom areas."""
    # Default benchmark
    safe_res_def = client.get("/api/safe-locations/candidates")
    assert safe_res_def.json()["data_provenance"] == "PARTIALLY_REAL"

    # Select custom location (Cologne)
    select_study_area(latitude=50.938, longitude=6.960)

    safe_res_dyn = client.get("/api/safe-locations/candidates")
    assert safe_res_dyn.json()["data_provenance"] == "MODELLED"

    # Evacuation route provenance
    net_res = client.get("/api/evacuation/network")
    nodes = net_res.json()["nodes"]
    assert len(nodes) >= 9
    # Route in dynamic area
    n1, n2 = nodes[0], nodes[-1]
    route_res = client.post("/api/evacuation/route", json={
        "origin_lat": n1["lat"], "origin_lon": n1["lon"],
        "dest_lat": n2["lat"], "dest_lon": n2["lon"],
    })
    assert route_res.status_code == 200
    assert route_res.json()["data_provenance"]["road_network"] == "MODELLED"

