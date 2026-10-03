"""
Multi-Scenario Flood Simulation & Comparison Service
===================================================
Coordinates scenario simulation across the unified QuantumFlood AI disaster
pipeline and produces side-by-side comparative analytics.

Pipeline:
  SCENARIO INPUTS (water_level, inflow, rainfall)
       ↓
  RISK ENGINE (attenuated per-zone risk)
       ↓
  SENSOR OPTIMIZATION (weighted maximum coverage)
       ↓
  CONNECTIVITY ANALYSIS (budgeted comm nodes)
       ↓
  SAFE LOCATION FINDER (MCDA lower-risk evaluation)
       ↓
  EVACUATION ROUTING (risk-penalised routing)
       ↓
  RESOURCE ALLOCATION (constrained knapsack allocation)
       ↓
  UNIFIED RESPONSE PLAN & CROSS-SCENARIO METRIC MATRIX
"""
import logging
from dataclasses import asdict
from typing import List, Dict, Any, Optional

from app.risk.risk_engine import generate_zone_risk_map
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.evaluator import build_coverage_summary
from app.recommendations.recommendation_engine import generate_recommendations
from app.services.safe_location_service import evaluate_safe_locations
from app.services.evacuation_service import calculate_evacuation_routes
from app.services.resource_allocation_service import allocate_emergency_resources
from app.services.pipeline_state import state
from app.config.settings import (
    DEFAULT_NUM_SENSORS,
    DEFAULT_COVERAGE_RADIUS_KM,
    DEFAULT_COMM_RANGE_KM,
    DEFAULT_MAX_COMM_NODES,
)

logger = logging.getLogger(__name__)

SCENARIO_PRESETS = [
    {
        "id": "baseline",
        "name": "Scenario A — Baseline Conditions",
        "description": "Historical normal monsoon water level and inflow within manageable riverbank confines.",
        "water_level_m": 8.8,
        "inflow_ktcmd": 380.0,
        "rainfall_mm_24h": 32.0,
        "severity": "LOW_TO_MODERATE",
    },
    {
        "id": "moderate",
        "name": "Scenario B — Moderate Flood",
        "description": "Elevated discharge approaching warning datum with noticeable localized low-lying water ingress.",
        "water_level_m": 11.6,
        "inflow_ktcmd": 710.0,
        "rainfall_mm_24h": 82.0,
        "severity": "MODERATE_TO_HIGH",
    },
    {
        "id": "severe",
        "name": "Scenario C — Severe Flood Event",
        "description": "Extreme inflow event matching high-discharge historical peaks at Prakasam Barrage.",
        "water_level_m": 14.2,
        "inflow_ktcmd": 1050.0,
        "rainfall_mm_24h": 138.0,
        "severity": "CRITICAL",
    },
]


def run_scenario_pipeline(
    scenario_id: str,
    name: str,
    water_level_m: float,
    inflow_ktcmd: float,
    rainfall_mm_24h: float,
    resolution: str = "default",
    num_sensors: int = DEFAULT_NUM_SENSORS,
    coverage_radius_km: float = DEFAULT_COVERAGE_RADIUS_KM,
    comm_range_km: float = DEFAULT_COMM_RANGE_KM,
    max_comm_nodes: int = DEFAULT_MAX_COMM_NODES,
    rescue_teams: int = 5,
    medical_teams: int = 3,
    relief_units: int = 4,
    emergency_vehicles: int = 4,
) -> Dict[str, Any]:
    """
    Executes the entire disaster response pipeline deterministically for a single scenario.
    Each stage is independently error-handled: a failure in one stage produces partial
    results with error details instead of crashing the entire pipeline.
    """
    pipeline_errors = []

    # 1. Risk Engine (critical — downstream stages depend on this)
    try:
        risk_map = generate_zone_risk_map(water_level_m, inflow_ktcmd, rainfall_mm_24h, resolution=resolution)
        zones = risk_map["zones"]
        zone_risk_lookup = {z["zone_id"]: z["risk_score"] for z in zones}
    except Exception as e:
        logger.error("Scenario '%s' risk engine failed: %s", scenario_id, e)
        # Risk engine is foundational — if it fails, we cannot continue.
        return {
            "scenario_id": scenario_id, "name": name,
            "status": "PIPELINE_ERROR",
            "failed_stage": "risk_engine",
            "error": str(e),
            "inputs": {"water_level_m": water_level_m, "inflow_ktcmd": inflow_ktcmd,
                       "rainfall_mm_24h": rainfall_mm_24h, "resolution": resolution},
            "metrics": {}, "pipeline_artifacts": {}
        }

    # 2. Optimization Engine (Sensors)
    opt_result = None
    connectivity_result = None
    coverage_summary = None
    recommendations = None
    try:
        candidates = generate_candidates(zone_risk_lookup, resolution)
        engine = ClassicalOptimizationEngine()
        opt_result = engine.optimize(candidates, zones, coverage_radius_km, num_sensors)

        # 3. Connectivity Analysis (depends on optimization)
        connectivity_result = analyze_connectivity(opt_result.selected_sensors, comm_range_km, max_comm_nodes)
        coverage_summary = build_coverage_summary(opt_result, connectivity_result, zones)
        recommendations = generate_recommendations(risk_map, opt_result, connectivity_result)
    except Exception as e:
        logger.error("Scenario '%s' optimization/connectivity failed: %s", scenario_id, e)
        pipeline_errors.append({"stage": "optimization_connectivity", "error": str(e)})

    # 4. Safe Locations
    safe_locations_res = None
    top_safe = None
    try:
        safe_locations_res = evaluate_safe_locations(zones)
        top_safe = safe_locations_res["locations"][0] if safe_locations_res["locations"] else None
    except Exception as e:
        logger.error("Scenario '%s' safe locations failed: %s", scenario_id, e)
        pipeline_errors.append({"stage": "safe_locations", "error": str(e)})

    # 5. Evacuation Routing (from most critical zone centroid to top recommended safe location)
    evac_result = None
    try:
        if top_safe:
            critical_zones = [z for z in zones if z["risk_level"] in ("CRITICAL", "HIGH")]
            origin_zone = critical_zones[0] if critical_zones else zones[0]

            evac_result = calculate_evacuation_routes(
                origin_lat=origin_zone["centroid"]["lat"],
                origin_lon=origin_zone["centroid"]["lon"],
                dest_lat=top_safe["lat"],
                dest_lon=top_safe["lon"],
                zones=zones,
                origin_name=f"Corridor Zone {origin_zone['zone_id']}",
                dest_name=top_safe["name"]
            )
    except Exception as e:
        logger.error("Scenario '%s' evacuation routing failed: %s", scenario_id, e)
        pipeline_errors.append({"stage": "evacuation_routing", "error": str(e)})

    # 6. Emergency Resource Allocation
    resource_alloc_res = None
    try:
        resource_alloc_res = allocate_emergency_resources(
            zones=zones,
            rescue_teams=rescue_teams,
            medical_teams=medical_teams,
            relief_units=relief_units,
            emergency_vehicles=emergency_vehicles
        )
    except Exception as e:
        logger.error("Scenario '%s' resource allocation failed: %s", scenario_id, e)
        pipeline_errors.append({"stage": "resource_allocation", "error": str(e)})

    # Key rollup metrics (safe against None results from failed stages)
    crit_count = sum(1 for z in zones if z["risk_level"] == "CRITICAL")
    high_count = sum(1 for z in zones if z["risk_level"] == "HIGH")
    mod_count = sum(1 for z in zones if z["risk_level"] == "MODERATE")
    low_count = sum(1 for z in zones if z["risk_level"] == "LOW")

    route_risk = (
        evac_result["primary_route"]["estimated_route_risk_score"]
        if evac_result and evac_result.get("primary_route") else 1.0
    )

    total_resources_needed = (crit_count * 2) + (high_count * 1)

    result = {
        "scenario_id": scenario_id,
        "name": name,
        "inputs": {
            "water_level_m": water_level_m,
            "inflow_ktcmd": inflow_ktcmd,
            "rainfall_mm_24h": rainfall_mm_24h,
            "resolution": resolution
        },
        "metrics": {
            "base_risk_level": risk_map["base_classification"]["overall_risk"],
            "critical_zones_count": crit_count,
            "high_zones_count": high_count,
            "moderate_zones_count": mod_count,
            "low_zones_count": low_count,
            "total_zones": len(zones),
            "sensor_coverage_percentage": opt_result.coverage_percentage if opt_result else 0.0,
            "critical_zone_coverage_percentage": opt_result.critical_zone_coverage_percentage if opt_result else 0.0,
            "connected_sensors_count": len(connectivity_result.connected_sensor_ids) if connectivity_result else 0,
            "disconnected_sensors_count": len(connectivity_result.disconnected_sensor_ids) if connectivity_result else 0,
            "connectivity_percentage": connectivity_result.connectivity_percentage if connectivity_result else 0.0,
            "primary_evac_route_risk": route_risk,
            "emergency_demand_index": total_resources_needed,
            "resources_serviced_zones": resource_alloc_res["summary"]["zones_serviced_count"] if resource_alloc_res else 0
        },
        "pipeline_artifacts": {
            "risk_map": risk_map,
            "optimization": asdict(opt_result) if opt_result else None,
            "connectivity": asdict(connectivity_result) if connectivity_result else None,
            "coverage_summary": coverage_summary,
            "recommendations": recommendations,
            "safe_locations": safe_locations_res,
            "evacuation": evac_result,
            "resource_allocation": resource_alloc_res
        }
    }

    if pipeline_errors:
        result["pipeline_errors"] = pipeline_errors

    return result


def compare_scenarios(scenario_configs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Simulates multiple scenarios and produces a side-by-side comparison matrix.
    """
    configs = scenario_configs or SCENARIO_PRESETS
    runs = []

    for cfg in configs:
        run = run_scenario_pipeline(
            scenario_id=cfg.get("id", "custom"),
            name=cfg.get("name", "Custom Scenario"),
            water_level_m=cfg["water_level_m"],
            inflow_ktcmd=cfg["inflow_ktcmd"],
            rainfall_mm_24h=cfg["rainfall_mm_24h"],
            resolution=cfg.get("resolution", "default")
        )
        runs.append(run)

    # Build comparison table rows
    comparison_table = [
        {
            "metric": "Base Forecast Risk Level",
            **{r["scenario_id"]: r["metrics"]["base_risk_level"] for r in runs}
        },
        {
            "metric": "Critical Risk Zones",
            **{r["scenario_id"]: r["metrics"]["critical_zones_count"] for r in runs}
        },
        {
            "metric": "High Risk Zones",
            **{r["scenario_id"]: r["metrics"]["high_zones_count"] for r in runs}
        },
        {
            "metric": "Sensor Area Coverage (%)",
            **{r["scenario_id"]: f"{r['metrics']['sensor_coverage_percentage']}%" for r in runs}
        },
        {
            "metric": "Critical Zone Coverage (%)",
            **{r["scenario_id"]: f"{r['metrics']['critical_zone_coverage_percentage']}%" for r in runs}
        },
        {
            "metric": "Connected Sensors",
            **{r["scenario_id"]: f"{r['metrics']['connected_sensors_count']} / {r['metrics']['connected_sensors_count'] + r['metrics']['disconnected_sensors_count']}" for r in runs}
        },
        {
            "metric": "Estimated Evacuation Route Risk",
            **{r["scenario_id"]: r["metrics"]["primary_evac_route_risk"] for r in runs}
        },
        {
            "metric": "Emergency Response Demand Index",
            **{r["scenario_id"]: r["metrics"]["emergency_demand_index"] for r in runs}
        },
    ]

    return {
        "scenarios": runs,
        "comparison_table": comparison_table,
        "total_scenarios": len(runs)
    }


def activate_scenario_in_pipeline(scenario_id: str, custom_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Activates a scenario, updating the global system state (Risk Map, Sensor Placement,
    Connectivity, Recommendations) so that all pages reflect the selected scenario!
    """
    preset = next((p for p in SCENARIO_PRESETS if p["id"] == scenario_id), None)
    if not preset and not custom_params:
        raise ValueError(f"Unknown scenario ID '{scenario_id}' and no custom parameters provided.")

    params = custom_params or preset

    run = run_scenario_pipeline(
        scenario_id=params.get("id", scenario_id),
        name=params.get("name", "Active Scenario"),
        water_level_m=params["water_level_m"],
        inflow_ktcmd=params["inflow_ktcmd"],
        rainfall_mm_24h=params["rainfall_mm_24h"],
        resolution=params.get("resolution", "default")
    )

    arts = run["pipeline_artifacts"]

    # Propagate into pipeline state
    state.latest_risk_map = arts["risk_map"]
    state.latest_optimization = arts["optimization"]
    state.latest_connectivity = arts["connectivity"]
    state.latest_recommendations = arts["recommendations"]

    return {
        "status": "ACTIVATED",
        "scenario_id": run["scenario_id"],
        "name": run["name"],
        "metrics": run["metrics"],
        "message": f"Scenario '{run['name']}' activated. Risk and infrastructure pipeline updated across dashboard."
    }
