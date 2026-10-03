import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.coverage_matrix import haversine_km
from app.optimization.connectivity_analyzer import analyze_connectivity


def make_zones():
    # 4 zones in a line, 1km apart, alternating risk
    return [
        {"zone_id": "Z1", "centroid": {"lat": 16.50, "lon": 80.60}, "risk_level": "CRITICAL", "risk_score": 4},
        {"zone_id": "Z2", "centroid": {"lat": 16.51, "lon": 80.60}, "risk_level": "LOW", "risk_score": 1},
        {"zone_id": "Z3", "centroid": {"lat": 16.52, "lon": 80.60}, "risk_level": "HIGH", "risk_score": 3},
        {"zone_id": "Z4", "centroid": {"lat": 16.53, "lon": 80.60}, "risk_level": "LOW", "risk_score": 1},
    ]


def make_candidates():
    zones = make_zones()
    return [
        {"candidate_id": f"C{i+1}", "lat": z["centroid"]["lat"], "lon": z["centroid"]["lon"],
         "zone_id": z["zone_id"], "risk_weight": z["risk_score"], "near_river": True}
        for i, z in enumerate(zones)
    ]


def test_haversine_distance_known_points():
    # ~1 degree latitude at the equator ~ 111km; sanity check order of magnitude
    d = haversine_km(16.50, 80.60, 16.51, 80.60)
    assert 0.5 < d < 2.0  # ~1.1km for 0.01 degree lat


def test_optimizer_prioritises_critical_zone():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=1)
    # With only 1 sensor, the greedy algorithm must pick the CRITICAL zone (Z1)
    assert result.num_sensors_selected == 1
    assert "Z1" in result.selected_sensors[0]["covered_zone_ids"]


def test_optimizer_full_budget_covers_all_zones():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    assert result.coverage_percentage == 100.0
    assert result.critical_zone_coverage_percentage == 100.0


def test_connectivity_all_within_range():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    # comm range large enough to cover the whole ~3.3km line
    connectivity = analyze_connectivity(opt_result.selected_sensors, comm_range_km=10.0)
    assert connectivity.connectivity_percentage == 100.0
    assert len(connectivity.disconnected_sensor_ids) == 0


def test_connectivity_detects_disconnected_sensor():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    # very short comm range should disconnect at least one far sensor
    connectivity = analyze_connectivity(opt_result.selected_sensors, comm_range_km=0.5)
    assert len(connectivity.comm_nodes) >= 2


def test_connectivity_respects_limited_comm_node_budget():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    # Short comm range needs >=2 nodes for full connectivity; force a budget
    # of exactly 1 node and confirm the system respects it (UC-067: limited
    # communication nodes) rather than silently adding more nodes anyway.
    connectivity = analyze_connectivity(opt_result.selected_sensors, comm_range_km=0.5, max_comm_nodes=1)
    assert connectivity.comm_nodes_used <= 1
    assert connectivity.max_comm_nodes == 1
    assert connectivity.budget_exhausted is True
    assert len(connectivity.disconnected_sensor_ids) > 0
    assert connectivity.connectivity_percentage < 100.0


def test_connectivity_budget_not_exhausted_when_sufficient():
    zones = make_zones()
    candidates = make_candidates()
    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    connectivity = analyze_connectivity(opt_result.selected_sensors, comm_range_km=10.0, max_comm_nodes=4)
    assert connectivity.budget_exhausted is False
    assert connectivity.connectivity_percentage == 100.0


def test_naive_topk_optimizer_matches_interface():
    from app.optimization.classical_optimizer import NaiveTopKOptimizer
    zones = make_zones()
    candidates = make_candidates()
    engine = NaiveTopKOptimizer()
    result = engine.optimize(candidates, zones, radius_km=0.5, num_sensors=1)
    # With only 1 sensor, individual-score ranking must also pick the
    # CRITICAL zone (Z1 has the highest individual weighted coverage here).
    assert result.num_sensors_selected == 1
    assert "Z1" in result.selected_sensors[0]["covered_zone_ids"]
    assert result.engine_type == "classical_naive_topk"


def test_greedy_and_naive_agree_when_no_overlap_and_budget_covers_all():
    from app.optimization.classical_optimizer import NaiveTopKOptimizer
    zones = make_zones()
    candidates = make_candidates()
    greedy = ClassicalOptimizationEngine().optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    naive = NaiveTopKOptimizer().optimize(candidates, zones, radius_km=0.5, num_sensors=4)
    # Full budget with no real competition for coverage -> both should reach 100%
    assert greedy.coverage_percentage == 100.0
    assert naive.coverage_percentage == 100.0
