from typing import Optional, List
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
    from app.services.study_area_service import resolve_study_area_context
    from app.services.analysis_store import analysis_store
    from app.gis.geo_loader import get_risk_zone_geometry
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle and not req.zones and not req.study_area:
            raise HTTPException(status_code=404, detail=f"Analysis '{aid}' not found.")

    if req.study_area:
        study_area_ctx = resolve_study_area_context(study_area_payload=req.study_area, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    elif bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]
    else:
        try:
            study_area_ctx = resolve_study_area_context(study_area_payload=None, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if req.zones:
        zones = req.zones
        resolution = req.zones[0].get("resolution", "default") if req.zones else "default"
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"]["zones"]
        resolution = bundle["risk_map"].get("resolution", "default")
    elif req.study_area:
        resolution = "default"
        zones = get_risk_zone_geometry(resolution, study_area=study_area_ctx)
        for z in zones:
            if "risk_score" not in z:
                z["risk_score"] = 5.0
            if "risk_level" not in z:
                z["risk_level"] = "MODERATE"
    elif (ENABLE_LEGACY_SHARED_STATE or not aid) and state.latest_risk_map is not None:
        zones = state.latest_risk_map["zones"]
        resolution = state.latest_risk_map.get("resolution", "default")
    else:
        raise HTTPException(status_code=400, detail="No risk map available for this analysis. Call POST /api/risk/generate first or supply study_area / zones.")

    zone_risk_lookup = {z["zone_id"]: z.get("risk_score", 5.0) for z in zones}
    candidates = generate_candidates(zone_risk_lookup, resolution, study_area=study_area_ctx)

    engine = ClassicalOptimizationEngine()
    opt_result = engine.optimize(candidates, zones, req.coverage_radius_km, req.num_sensors)

    connectivity_result = analyze_connectivity(opt_result.selected_sensors, req.comm_range_km, req.max_comm_nodes)

    coverage_summary = build_coverage_summary(opt_result, connectivity_result, zones)
    target_risk_map = {
        "zones": zones,
        "resolution": resolution,
        "base_classification": (
            (bundle["risk_map"].get("base_classification") if bundle and "risk_map" in bundle and "base_classification" in bundle["risk_map"] else None)
            or (state.latest_risk_map.get("base_classification") if ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map and "base_classification" in state.latest_risk_map else None)
            or {"overall_risk": "MODERATE", "explanation": "Request-scoped study-area evaluation."}
        ),
    }
    recommendations = generate_recommendations(target_risk_map, opt_result, connectivity_result)

    if aid:
        analysis_store.update_field(aid, "optimization", asdict(opt_result))
        analysis_store.update_field(aid, "connectivity", asdict(connectivity_result))
        analysis_store.update_field(aid, "recommendations", recommendations)
        analysis_store.update_field(aid, "optimization_params", req.model_dump())

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_optimization = asdict(opt_result)
        state.latest_connectivity = asdict(connectivity_result)
        state.latest_recommendations = recommendations
        state.optimization_params = req.model_dump()

    return {
        "optimization": asdict(opt_result),
        "connectivity": asdict(connectivity_result),
        "coverage_summary": coverage_summary,
        "candidates_generated": len(candidates),
        "params": req.model_dump(),
        "study_area": study_area_ctx,
        "analysis_id": aid,
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
    from app.services.study_area_service import resolve_study_area_context
    from app.gis.geo_loader import get_risk_zone_geometry
    from app.services.analysis_store import analysis_store
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle and not req.zones and not req.study_area:
            raise HTTPException(status_code=404, detail=f"Analysis session '{aid}' not found.")

    if req.study_area:
        study_area_ctx = resolve_study_area_context(study_area_payload=req.study_area, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    elif bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]
    else:
        try:
            study_area_ctx = resolve_study_area_context(study_area_payload=None, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if req.zones:
        zones = req.zones
        resolution = req.zones[0].get("resolution", "default") if req.zones else "default"
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"]["zones"]
        resolution = bundle["risk_map"].get("resolution", "default")
    elif req.study_area:
        resolution = "default"
        zones = get_risk_zone_geometry(resolution, study_area=study_area_ctx)
        for z in zones:
            if "risk_score" not in z:
                z["risk_score"] = 5.0
            if "risk_level" not in z:
                z["risk_level"] = "MODERATE"
    elif (ENABLE_LEGACY_SHARED_STATE or not aid) and state.latest_risk_map is not None:
        zones = state.latest_risk_map["zones"]
        resolution = state.latest_risk_map.get("resolution", "default")
    else:
        raise HTTPException(status_code=400, detail="No risk map available for this analysis. Call POST /api/risk/generate first or supply study_area / zones.")

    zone_risk_lookup = {z["zone_id"]: z.get("risk_score", 5.0) for z in zones}
    raw_candidates = generate_candidates(zone_risk_lookup, resolution, study_area=study_area_ctx)

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
            min_distance_km=req.min_distance_km,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quantum QAOA optimization failed: {str(e)}")

    if aid:
        analysis_store.update_field(aid, "quantum_optimization", {
            "optimization": asdict(opt_result),
            "quantum": q_result.to_dict(),
        })

    return {
        "optimization": asdict(opt_result),
        "quantum": q_result.to_dict(),
        "candidates_generated": len(raw_candidates),
        "candidates_evaluated": len(candidates),
        "params": req.model_dump(),
        "study_area": study_area_ctx,
        "analysis_id": aid,
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
    from app.services.study_area_service import resolve_study_area_context
    from app.gis.geo_loader import get_risk_zone_geometry
    from app.services.analysis_store import analysis_store
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle and not req.zones and not req.study_area:
            raise HTTPException(status_code=404, detail=f"Analysis session '{aid}' not found.")

    if req.study_area:
        study_area_ctx = resolve_study_area_context(study_area_payload=req.study_area, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
    elif bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]
    else:
        try:
            study_area_ctx = resolve_study_area_context(study_area_payload=None, allow_fallback=ENABLE_LEGACY_SHARED_STATE or not aid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if req.zones:
        zones = req.zones
        resolution = req.zones[0].get("resolution", "default") if req.zones else "default"
    elif bundle and "risk_map" in bundle:
        zones = bundle["risk_map"]["zones"]
        resolution = bundle["risk_map"].get("resolution", "default")
    elif req.study_area:
        resolution = "default"
        zones = get_risk_zone_geometry(resolution, study_area=study_area_ctx)
        for z in zones:
            if "risk_score" not in z:
                z["risk_score"] = 5.0
            if "risk_level" not in z:
                z["risk_level"] = "MODERATE"
    elif (ENABLE_LEGACY_SHARED_STATE or not aid) and state.latest_risk_map is not None:
        zones = state.latest_risk_map["zones"]
        resolution = state.latest_risk_map.get("resolution", "default")
    else:
        raise HTTPException(status_code=400, detail="No risk map available for this analysis. Call POST /api/risk/generate first or supply study_area / zones.")

    zone_risk_lookup = {z["zone_id"]: z.get("risk_score", 5.0) for z in zones}
    raw_candidates = generate_candidates(zone_risk_lookup, resolution, study_area=study_area_ctx)

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
            min_distance_km=req.min_distance_km,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Solver comparison failed: {str(e)}")

    comparison_report["total_candidates_pool"] = len(raw_candidates)
    comparison_report["study_area"] = study_area_ctx
    comparison_report["analysis_id"] = aid
    return comparison_report


@router.get("/optimization/results")
def get_optimization_results(analysis_id: Optional[str] = None):
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    if analysis_id:
        from app.services.analysis_store import analysis_store
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "optimization" not in bundle:
            raise HTTPException(status_code=404, detail=f"No optimization results in analysis session '{analysis_id}'.")
        return {
            "optimization": bundle["optimization"],
            "connectivity": bundle.get("connectivity"),
            "params": bundle.get("optimization_params"),
            "analysis_id": analysis_id,
        }

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_optimization is None:
        raise HTTPException(status_code=404, detail="No optimisation results yet. Run POST /api/optimization/run.")
    return {
        "optimization": state.latest_optimization,
        "connectivity": state.latest_connectivity,
        "params": state.optimization_params,
    }


@router.get("/optimization/candidates")
def get_candidates(lat: float = None, lon: float = None, analysis_id: Optional[str] = None):
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    zone_risk_lookup = None
    resolution = "default"
    study_area_ctx = None

    if analysis_id:
        from app.services.analysis_store import analysis_store
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if bundle:
            if "risk_map" in bundle:
                zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in bundle["risk_map"]["zones"]}
                resolution = bundle["risk_map"].get("resolution", "default")
            if "study_area" in bundle:
                study_area_ctx = bundle["study_area"]

    if lat is not None and lon is not None:
        from app.services.study_area_service import resolve_study_area_context
        study_area_ctx = resolve_study_area_context(latitude=lat, longitude=lon, allow_fallback=ENABLE_LEGACY_SHARED_STATE)

    if zone_risk_lookup is None:
        if ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
            zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in state.latest_risk_map["zones"]}
            resolution = state.latest_risk_map.get("resolution", "default")
        elif not study_area_ctx and not ENABLE_LEGACY_SHARED_STATE:
            from app.services.study_area_service import resolve_study_area_context
            try:
                study_area_ctx = resolve_study_area_context(allow_fallback=True)
            except Exception:
                study_area_ctx = None

    candidates = generate_candidates(zone_risk_lookup, resolution, study_area=study_area_ctx)
    return {"candidates": candidates, "count": len(candidates), "analysis_id": analysis_id}


@router.post("/optimization/experiments/run")
def run_experiments(req: ExperimentRunRequest):
    """
    Step 12-14: runs a reproducible experiment suite comparing Approach A (greedy)
    vs Approach B (naive top-K) on the analysis risk map.
    """
    from app.config.settings import ENABLE_LEGACY_SHARED_STATE

    bundle = None
    if req.analysis_id:
        from app.services.analysis_store import analysis_store
        if not analysis_store.is_valid_id(req.analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(req.analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{req.analysis_id}' not found.")

    if bundle and "risk_map" in bundle:
        zones = bundle["risk_map"]["zones"]
    elif ENABLE_LEGACY_SHARED_STATE and state.latest_risk_map is not None:
        zones = state.latest_risk_map["zones"]
    else:
        raise HTTPException(
            status_code=400,
            detail="No risk map available for this analysis. Provide 'analysis_id' with an existing risk map."
        )

    configs = [c.model_dump() for c in req.configs] if req.configs else None
    run_record = run_experiment_suite(zones, configs, req.resolution)
    if req.analysis_id:
        run_record["analysis_id"] = req.analysis_id
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
