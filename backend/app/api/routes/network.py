from typing import Optional
from fastapi import APIRouter, HTTPException
from dataclasses import asdict

from app.schemas.schemas import NetworkAnalyzeRequest
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.evaluator import build_coverage_summary
from app.services.pipeline_state import state
from app.services.analysis_store import analysis_store

from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.post("/network/analyze")
def analyze_network(req: NetworkAnalyzeRequest):
    aid = req.analysis_id
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{aid}' not found.")
        if "optimization" not in bundle or not bundle["optimization"].get("selected_sensors"):
            raise HTTPException(status_code=400, detail=f"Run sensor optimisation first for analysis '{aid}' (POST /api/optimization/run).")

        selected_sensors = bundle["optimization"]["selected_sensors"]
        connectivity_result = analyze_connectivity(selected_sensors, req.comm_range_km, req.max_comm_nodes)
        conn_dict = asdict(connectivity_result)
        analysis_store.update_field(aid, "connectivity", conn_dict)

        if ENABLE_LEGACY_SHARED_STATE:
            state.latest_connectivity = conn_dict

        zones = bundle.get("risk_map", {}).get("zones", [])
        cov = _build_cov_from(bundle["optimization"], conn_dict, zones) if zones else None
        return {"connectivity": conn_dict, "coverage_summary": cov, "analysis_id": aid}

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' parameter in multi-user mode.")

    if state.latest_optimization is None:
        raise HTTPException(status_code=400, detail="Run sensor optimisation first (POST /api/optimization/run).")

    connectivity_result = analyze_connectivity(
        state.latest_optimization["selected_sensors"], req.comm_range_km, req.max_comm_nodes
    )
    state.latest_connectivity = asdict(connectivity_result)

    return {"connectivity": state.latest_connectivity, "coverage_summary": _build_cov()}


@router.get("/network/results")
def get_network_results(analysis_id: Optional[str] = None):
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "connectivity" not in bundle:
            raise HTTPException(status_code=404, detail=f"No network analysis yet for analysis '{analysis_id}'.")
        return bundle["connectivity"]

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_connectivity is None:
        raise HTTPException(status_code=404, detail="No network analysis yet.")
    return state.latest_connectivity


@router.get("/coverage/analysis")
def coverage_analysis(analysis_id: Optional[str] = None):
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        if "optimization" not in bundle or "connectivity" not in bundle:
            raise HTTPException(status_code=404, detail=f"Run optimisation first for analysis '{analysis_id}' to produce coverage analysis.")
        zones = bundle.get("risk_map", {}).get("zones", [])
        return _build_cov_from(bundle["optimization"], bundle["connectivity"], zones)

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_optimization is None or state.latest_connectivity is None:
        raise HTTPException(status_code=404, detail="Run optimisation first to produce coverage analysis.")
    return _build_cov()


def _build_cov_from(opt_dict, conn_dict, zones):
    class _DictProxy:
        def __init__(self, d): self.__dict__.update(d)

    opt_proxy = _DictProxy(opt_dict)
    conn_proxy = _DictProxy(conn_dict)
    return build_coverage_summary(opt_proxy, conn_proxy, zones)


def _build_cov():
    """Build a coverage summary from the dict-based state objects using
    a lightweight adapter that provides attribute-style access for
    build_coverage_summary, which expects .coverage_percentage etc."""
    return _build_cov_from(state.latest_optimization, state.latest_connectivity, state.latest_risk_map["zones"])
