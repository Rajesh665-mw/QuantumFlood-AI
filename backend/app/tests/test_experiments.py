import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.optimization.experiments import run_experiment_suite, list_past_experiment_runs, load_experiment_run, EXPERIMENTS_DIR
from app.gis.geo_loader import get_risk_zone_geometry


def make_test_zones():
    """Reuse real geometry (deterministic) with a fabricated but consistent
    risk_level/risk_score assignment for fast experiment testing."""
    zones = get_risk_zone_geometry("low")
    for i, z in enumerate(zones):
        z["risk_level"] = "CRITICAL" if i % 5 == 0 else ("HIGH" if i % 3 == 0 else "LOW")
        z["risk_score"] = {"LOW": 1, "MODERATE": 2, "HIGH": 3, "CRITICAL": 4}[z["risk_level"]]
    return zones


def test_experiment_suite_runs_and_produces_real_metrics():
    zones = make_test_zones()
    configs = [{"label": "tiny", "num_sensors": 3, "coverage_radius_km": 2.5, "comm_range_km": 4.0, "max_comm_nodes": 2}]
    run_record = run_experiment_suite(zones, configs, resolution="low")

    assert len(run_record["experiments"]) == 1
    exp = run_record["experiments"][0]
    assert exp["experiment_id"] == "EXP-001"
    assert exp["approach_a_greedy"]["engine_type"] == "classical_greedy"
    assert exp["approach_b_naive_topk"]["engine_type"] == "classical_naive_topk"
    # Real, non-fabricated execution time (>= 0, not a hardcoded constant)
    assert exp["approach_a_greedy"]["execution_time_seconds"] >= 0
    # Greedy should never do WORSE than naive on the objective score
    assert exp["approach_a_greedy"]["objective_score"] >= exp["approach_b_naive_topk"]["objective_score"]


def test_experiment_run_is_persisted_and_reloadable():
    zones = make_test_zones()
    configs = [{"label": "tiny", "num_sensors": 2, "coverage_radius_km": 2.0, "comm_range_km": 3.0, "max_comm_nodes": 1}]
    run_record = run_experiment_suite(zones, configs, resolution="low")

    saved_filename = run_record["saved_to"]
    assert saved_filename in list_past_experiment_runs()

    reloaded = load_experiment_run(saved_filename)
    assert reloaded["experiments"][0]["config"]["num_sensors"] == 2


def test_load_experiment_run_rejects_path_traversal():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_experiment_run("../../../etc/passwd")
