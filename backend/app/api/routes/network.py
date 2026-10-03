from fastapi import APIRouter, HTTPException
from dataclasses import asdict

from app.schemas.schemas import NetworkAnalyzeRequest
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.evaluator import build_coverage_summary
from app.services.pipeline_state import state

router = APIRouter()


@router.post("/network/analyze")
def analyze_network(req: NetworkAnalyzeRequest):
    if state.latest_optimization is None:
        raise HTTPException(status_code=400, detail="Run sensor optimisation first (POST /api/optimization/run).")

    connectivity_result = analyze_connectivity(
        state.latest_optimization["selected_sensors"], req.comm_range_km, req.max_comm_nodes
    )
    state.latest_connectivity = asdict(connectivity_result)

    return {"connectivity": state.latest_connectivity, "coverage_summary": _build_cov()}


@router.get("/network/results")
def get_network_results():
    if state.latest_connectivity is None:
        raise HTTPException(status_code=404, detail="No network analysis yet.")
    return state.latest_connectivity


@router.get("/coverage/analysis")
def coverage_analysis():
    if state.latest_optimization is None or state.latest_connectivity is None:
        raise HTTPException(status_code=404, detail="Run optimisation first to produce coverage analysis.")
    return _build_cov()


def _build_cov():
    """Build a coverage summary from the dict-based state objects using
    a lightweight adapter that provides attribute-style access for
    build_coverage_summary, which expects .coverage_percentage etc."""

    class _DictProxy:
        def __init__(self, d): self.__dict__.update(d)

    opt_proxy = _DictProxy(state.latest_optimization)
    conn_proxy = _DictProxy(state.latest_connectivity)
    return build_coverage_summary(opt_proxy, conn_proxy, state.latest_risk_map["zones"])
