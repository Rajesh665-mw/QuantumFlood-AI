from fastapi import APIRouter, HTTPException
from app.schemas.schemas import NetworkFailureSimulateRequest
from app.services.network_resilience_service import simulate_network_failure
from app.services.pipeline_state import state
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.gis.geo_loader import get_risk_zone_geometry
from app.config.settings import DEFAULT_COMM_RANGE_KM, DEFAULT_MAX_COMM_NODES

router = APIRouter()


@router.post("/network/resilience/simulate")
def simulate_resilience(req: NetworkFailureSimulateRequest):
    """
    Simulates failure of user-selected communication node(s), identifies
    isolated sensors and affected critical zones, and computes optimal recovery relay placement.
    """
    sensors = []
    comm_nodes = []

    if state.latest_optimization is not None:
        sensors = state.latest_optimization.get("selected_sensors", [])

    if state.latest_connectivity is not None:
        comm_nodes = state.latest_connectivity.get("comm_nodes", [])

    if not sensors or not comm_nodes:
        # Generate initial sensor + connectivity setup if not yet performed
        zones = state.latest_risk_map.get("zones") if state.latest_risk_map else get_risk_zone_geometry("default")
        candidates = generate_candidates()
        engine = ClassicalOptimizationEngine()
        opt = engine.optimize(candidates, zones, 2.5, 8)
        sensors = opt.selected_sensors
        conn = analyze_connectivity(sensors, req.comm_range_km, DEFAULT_MAX_COMM_NODES)
        comm_nodes = conn.comm_nodes

    zones = state.latest_risk_map.get("zones") if state.latest_risk_map else None

    result = simulate_network_failure(
        selected_sensors=sensors,
        comm_nodes=comm_nodes,
        failed_node_ids=req.failed_node_ids,
        comm_range_km=req.comm_range_km,
        zones=zones
    )

    state.latest_resilience = result
    return result


@router.get("/network/resilience/latest")
def get_latest_resilience():
    """Returns the latest resilience simulation and recovery plan."""
    if state.latest_resilience is None:
        # Run a default simulation (no failed nodes)
        req = NetworkFailureSimulateRequest(failed_node_ids=[])
        return simulate_resilience(req)
    return state.latest_resilience
