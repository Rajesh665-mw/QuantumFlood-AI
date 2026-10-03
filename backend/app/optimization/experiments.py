"""
Optimization Experiment Framework (Steps 12-14)
=================================================
Turns the classical sensor/comm-node optimisation system into a measurable
scientific baseline: runs a batch of configurations, records ACTUAL results
(no hardcoded/fabricated values), and persists them reproducibly as JSON.

This is also the designated comparison point for the future quantum
optimiser: the same `zones` + `candidates` + config can later be handed to a
QuantumOptimizationEngine and the two experiment result sets compared
directly (CLASSICAL vs QUANTUM), without implementing anything quantum now.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.optimization.candidate_generator import generate_candidates
from app.optimization.classical_optimizer import ClassicalOptimizationEngine, NaiveTopKOptimizer
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.evaluator import build_coverage_summary
from app.config.settings import DATA_PROCESSED_DIR

EXPERIMENTS_DIR = DATA_PROCESSED_DIR / "experiments"
EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Default benchmark suite (Step 14: small / medium / large problem sizes).
# Kept modest so the default run stays fast for a classroom prototype.
DEFAULT_EXPERIMENT_CONFIGS = [
    {"label": "small", "num_sensors": 5, "coverage_radius_km": 2.5, "comm_range_km": 4.0, "max_comm_nodes": 2},
    {"label": "medium", "num_sensors": 10, "coverage_radius_km": 2.5, "comm_range_km": 4.0, "max_comm_nodes": 4},
    {"label": "large", "num_sensors": 20, "coverage_radius_km": 2.5, "comm_range_km": 4.0, "max_comm_nodes": 6},
]


def _run_single(engine, candidates: list, zones: list, config: dict) -> dict:
    t0 = time.perf_counter()
    opt_result = engine.optimize(candidates, zones, config["coverage_radius_km"], config["num_sensors"])
    connectivity = analyze_connectivity(opt_result.selected_sensors, config["comm_range_km"], config["max_comm_nodes"])
    elapsed_seconds = time.perf_counter() - t0

    coverage_summary = build_coverage_summary(opt_result, connectivity, zones)
    objective_score = opt_result.weighted_risk_coverage

    return {
        "engine_type": engine.engine_type,
        "objective_score": objective_score,
        "coverage_percentage": opt_result.coverage_percentage,
        "critical_zone_coverage_percentage": opt_result.critical_zone_coverage_percentage,
        "sensors_selected": opt_result.num_sensors_selected,
        "selected_sensor_ids": [s["candidate_id"] for s in opt_result.selected_sensors],
        "comm_nodes_used": connectivity.comm_nodes_used,
        "comm_node_ids": [n["comm_node_id"] for n in connectivity.comm_nodes],
        "connectivity_percentage": connectivity.connectivity_percentage,
        "uncovered_critical_zones": [
            zid for zid in opt_result.uncovered_priority_zone_ids
            if any(z["zone_id"] == zid and z["risk_level"] == "CRITICAL" for z in zones)
        ],
        "execution_time_seconds": round(elapsed_seconds, 5),
        "coverage_summary": coverage_summary,
    }


def run_experiment_suite(zones: list, configs: list = None, resolution: str = "default") -> dict:
    """
    Runs every config in `configs` (default: DEFAULT_EXPERIMENT_CONFIGS)
    through BOTH Approach A (greedy) and Approach B (naive top-K), so each
    experiment record directly compares the two classical methods on the
    identical candidate set. Persists the full run to a timestamped JSON
    file under data/processed/experiments/ for reproducibility.
    """
    configs = configs or DEFAULT_EXPERIMENT_CONFIGS
    zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in zones}
    candidates = generate_candidates(zone_risk_lookup, resolution)

    greedy_engine = ClassicalOptimizationEngine()
    naive_engine = NaiveTopKOptimizer()

    experiments = []
    for idx, config in enumerate(configs, start=1):
        experiment_id = f"EXP-{idx:03d}"
        greedy_result = _run_single(greedy_engine, candidates, zones, config)
        naive_result = _run_single(naive_engine, candidates, zones, config)

        experiments.append({
            "experiment_id": experiment_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": config,
            "num_candidates": len(candidates),
            "num_zones": len(zones),
            "approach_a_greedy": greedy_result,
            "approach_b_naive_topk": naive_result,
            "greedy_advantage_objective_score": round(
                greedy_result["objective_score"] - naive_result["objective_score"], 3
            ),
        })

    # Aggregate statistics across all experiment configs (scientific baseline summary)
    advantages = [e["greedy_advantage_objective_score"] for e in experiments]
    greedy_coverages = [e["approach_a_greedy"]["coverage_percentage"] for e in experiments]
    greedy_times = [e["approach_a_greedy"]["execution_time_seconds"] for e in experiments]
    naive_times = [e["approach_b_naive_topk"]["execution_time_seconds"] for e in experiments]

    import statistics
    aggregate_stats = {
        "total_experiments": len(experiments),
        "greedy_advantage": {
            "mean": round(statistics.mean(advantages), 3) if advantages else 0,
            "std": round(statistics.stdev(advantages), 3) if len(advantages) > 1 else 0,
            "min": round(min(advantages), 3) if advantages else 0,
            "max": round(max(advantages), 3) if advantages else 0,
            "greedy_wins": sum(1 for a in advantages if a > 0),
            "ties": sum(1 for a in advantages if a == 0),
            "naive_wins": sum(1 for a in advantages if a < 0),
        },
        "greedy_coverage_mean_pct": round(statistics.mean(greedy_coverages), 2) if greedy_coverages else 0,
        "mean_execution_time_greedy_s": round(statistics.mean(greedy_times), 5) if greedy_times else 0,
        "mean_execution_time_naive_s": round(statistics.mean(naive_times), 5) if naive_times else 0,
    }

    run_record = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "resolution": resolution,
        "aggregate_statistics": aggregate_stats,
        "experiments": experiments,
    }

    filename = f"experiment_run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path = EXPERIMENTS_DIR / filename
    with open(out_path, "w") as f:
        json.dump(run_record, f, indent=2)

    run_record["saved_to"] = str(out_path.name)
    return run_record


def list_past_experiment_runs() -> list:
    """Returns filenames of previously saved experiment runs (reproducibility - Step 8/14)."""
    return sorted(p.name for p in EXPERIMENTS_DIR.glob("experiment_run_*.json"))


def load_experiment_run(filename: str) -> dict:
    # Guard against path traversal - only allow simple filenames within
    # EXPERIMENTS_DIR that match our own naming scheme.
    safe_name = Path(filename).name
    if not safe_name.startswith("experiment_run_") or not safe_name.endswith(".json"):
        raise FileNotFoundError(f"No such experiment run: {filename}")
    path = EXPERIMENTS_DIR / safe_name
    if not path.exists():
        raise FileNotFoundError(f"No such experiment run: {filename}")
    with open(path, "r") as f:
        return json.load(f)
