from fastapi import APIRouter, HTTPException
from app.schemas.schemas import ScenarioCompareRequest, ScenarioActivateRequest, CustomScenarioInput
from app.services.scenario_service import SCENARIO_PRESETS, compare_scenarios, activate_scenario_in_pipeline, run_scenario_pipeline
from app.services.pipeline_state import state

router = APIRouter()


@router.get("/scenarios/presets")
def get_scenario_presets():
    """Returns the standard pre-configured scenario definitions (Baseline, Moderate, Severe)."""
    return {
        "presets": SCENARIO_PRESETS,
        "active_scenario_id": state.active_scenario.get("scenario_id") if state.active_scenario else "baseline"
    }


@router.post("/scenarios/run")
def run_single_scenario(req: CustomScenarioInput):
    """Executes the full disaster response pipeline for a specific scenario."""
    res = run_scenario_pipeline(
        scenario_id=req.id,
        name=req.name,
        water_level_m=req.water_level_m,
        inflow_ktcmd=req.inflow_ktcmd,
        rainfall_mm_24h=req.rainfall_mm_24h,
        resolution=req.resolution
    )
    return res


@router.post("/scenarios/compare")
def compare_flood_scenarios(req: ScenarioCompareRequest):
    """
    Simulates multiple flood scenarios and returns a side-by-side comparative matrix.
    """
    configs = [s.dict() for s in req.scenarios] if req.scenarios else None
    comparison = compare_scenarios(configs)
    return comparison


@router.post("/scenarios/activate")
def activate_scenario(req: ScenarioActivateRequest):
    """
    Activates a scenario, updating the pipeline state across the entire system.
    """
    custom = req.custom_params.dict() if req.custom_params else None
    try:
        activation = activate_scenario_in_pipeline(req.scenario_id, custom)
        state.active_scenario = activation
        return activation
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
