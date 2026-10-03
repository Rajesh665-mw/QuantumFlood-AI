from fastapi import APIRouter, HTTPException
from dataclasses import asdict

from app.schemas.schemas import (
    OptimizationRunRequest,
    ExperimentRunRequest,
    QuantumOptimizationRunRequest,
    OptimizationCompareRequest,
)
from app.optimization.candidate_generator import generate_candidates
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.quantum.quantum_optimizer import QuantumOptimizationEngine
from app.optimization.comparison_engine import OptimizationComparisonEngine
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.evaluator import build_coverage_summary
from app.optimization.experiments import run_experiment_suite, list_past_experiment_runs, load_experiment_run
from app.recommendations.recommendation_engine import generate_recommendations
from app.services.pipeline_state import state

router = APIRouter()


@router.post("/optimization/run")
def run_optimization(req: OptimizationRunRequest):
    if state.latest_risk_map is None:
        raise HTTPException(status_code=400, detail="No risk map available. Call POST /api/risk/generate first.")

    zones = state.latest_risk_map["zones"]
    resolution = state.latest_risk_map.get("resolution", "default")
    zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in zones}
    candidates = generate_candidates(zone_risk_lookup, resolution)

    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, req.coverage_radius_km, req.num_sensors)

    connectivity_result = analyze_connectivity(opt_result.selected_sensors, req.comm_range_km, req.max_comm_nodes)

    coverage_summary = build_coverage_summary(opt_result, connectivity_result, zones)
    recommendations = generate_recommendations(state.latest_risk_map, opt_result, connectivity_result)

    state.latest_optimization = asdict(opt_result)
    state.latest_connectivity = asdict(connectivity_result)
    state.latest_recommendations = recommendations
    state.optimization_params = req.dict()

    return {
        "optimization": asdict(opt_result),
        "connectivity": asdict(connectivity_result),
        "coverage_summary": coverage_summary,
        "candidates_generated": len(candidates),
        "params": req.dict(),
    }


def _filter_top_candidates(
    candidates: list,
    zones: list,
    coverage_radius_km: float,
    max_n: int,
) -> list:
    """
    Subsets the candidate pool to the top max_n most promising sensor sites
    (ranked by individual risk-weighted coverage) for statevector quantum simulation.
    """
    if len(candidates) <= max_n:
        return candidates
    
    from app.optimization.classical_optimizer import _compute_candidate_coverage, _compute_zone_weights
    cand_coverage = _compute_candidate_coverage(candidates, zones, coverage_radius_km)
    zone_weights = _compute_zone_weights(zones)
    
    def score(c):
        covered = cand_coverage.get(c["candidate_id"], set())
        return sum(zone_weights.get(zid, 0.0) for zid in covered)
    
    sorted_candidates = sorted(candidates, key=score, reverse=True)
    return sorted_candidates[:max_n]


@router.post("/optimization/quantum")
def run_quantum_optimization(req: QuantumOptimizationRunRequest):
    """
    Executes QAOA quantum optimization for sensor placement on the current risk map.
    Returns both standard optimization format and rich quantum diagnostics.
    """
    if state.latest_risk_map is None:
        raise HTTPException(status_code=400, detail="No risk map available. Call POST /api/risk/generate first.")

    zones = state.latest_risk_map["zones"]
    resolution = state.latest_risk_map.get("resolution", "default")
    zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in zones}
    raw_candidates = generate_candidates(zone_risk_lookup, resolution)

    # Filter to top candidates suitable for local statevector simulation
    candidates = _filter_top_candidates(raw_candidates, zones, req.coverage_radius_km, req.max_candidates)
    effective_k = min(req.num_sensors, len(candidates))

    q_engine = QuantumOptimizationEngine()
    try:
        opt_result, q_result = q_engine.optimize(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=req.coverage_radius_km,
            num_sensors=effective_k,
            p=req.p,
            shots=req.shots,
            seed=req.seed,
            formulation_mode=req.formulation_mode,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quantum QAOA optimization failed: {str(e)}")

    return {
        "optimization": asdict(opt_result),
        "quantum": q_result.to_dict(),
        "candidates_generated": len(raw_candidates),
        "candidates_evaluated": len(candidates),
        "params": req.dict(),
    }


@router.post("/optimization/compare")
def compare_solvers(req: OptimizationCompareRequest):
    """
    Executes an identical sensor-placement problem across:
      1. Classical Greedy Optimizer
      2. Quantum QAOA Optimizer
      3. Exhaustive Global Optimum (if candidate count N <= 12)
    Provides an objective side-by-side performance audit.
    """
    if state.latest_risk_map is None:
        raise HTTPException(status_code=400, detail="No risk map available. Call POST /api/risk/generate first.")

    zones = state.latest_risk_map["zones"]
    resolution = state.latest_risk_map.get("resolution", "default")
    zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in zones}
    raw_candidates = generate_candidates(zone_risk_lookup, resolution)

    candidates = _filter_top_candidates(raw_candidates, zones, req.coverage_radius_km, req.max_candidates)
    effective_k = min(req.num_sensors, len(candidates))

    comparator = OptimizationComparisonEngine()
    try:
        comparison_report = comparator.compare(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=req.coverage_radius_km,
            num_sensors=effective_k,
            p=req.p,
            shots=req.shots,
            seed=req.seed,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solver comparison failed: {str(e)}")

    comparison_report["total_candidates_pool"] = len(raw_candidates)
    return comparison_report


@router.get("/optimization/results")
def get_optimization_results():
    if state.latest_optimization is None:
        raise HTTPException(status_code=404, detail="No optimisation results yet. Run POST /api/optimization/run.")
    return {
        "optimization": state.latest_optimization,
        "connectivity": state.latest_connectivity,
        "params": state.optimization_params,
    }


@router.get("/optimization/candidates")
def get_candidates():
    zone_risk_lookup = None
    resolution = "default"
    if state.latest_risk_map is not None:
        zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in state.latest_risk_map["zones"]}
        resolution = state.latest_risk_map.get("resolution", "default")
    candidates = generate_candidates(zone_risk_lookup, resolution)
    return {"candidates": candidates, "count": len(candidates)}


@router.post("/optimization/experiments/run")
def run_experiments(req: ExperimentRunRequest):
    """
    Step 12-14: runs a reproducible experiment suite (default small/medium/
    large problem sizes, or a custom config list) comparing Approach A
    (greedy) vs Approach B (naive top-K) on the CURRENT risk map. Every
    metric is computed live - nothing here is hardcoded or fabricated.
    Results are persisted as JSON under data/processed/experiments/.
    """
    if state.latest_risk_map is None:
        raise HTTPException(status_code=400, detail="No risk map available. Call POST /api/risk/generate first.")

    zones = state.latest_risk_map["zones"]
    configs = [c.dict() for c in req.configs] if req.configs else None
    run_record = run_experiment_suite(zones, configs, req.resolution)
    return run_record


@router.get("/optimization/experiments/results")
def list_experiments():
    return {"runs": list_past_experiment_runs()}


@router.get("/optimization/experiments/results/{filename}")
def get_experiment_run(filename: str):
    try:
        return load_experiment_run(filename)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
