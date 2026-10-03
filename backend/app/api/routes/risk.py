from fastapi import APIRouter, HTTPException
from app.schemas.schemas import RiskGenerateRequest
from app.risk.risk_engine import generate_zone_risk_map
from app.services.pipeline_state import state
from app.services.data_service import get_clean_dataset

router = APIRouter()


@router.post("/risk/generate")
def generate_risk(req: RiskGenerateRequest):
    water_level = req.water_level_m
    inflow = req.inflow_ktcmd
    rainfall = req.rainfall_mm_24h

    forecast_source = None
    if req.use_latest_forecast and (water_level is None or inflow is None or rainfall is None):
        target_forecast = state.latest_forecast
        source_name = "classical"
        if req.forecast_model_preference == "qml":
            if state.latest_qml_forecast is not None:
                target_forecast = state.latest_qml_forecast
                source_name = "qml"
            else:
                target_forecast = state.latest_forecast
                source_name = "classical_fallback"

        if target_forecast is not None:
            water_level = water_level if water_level is not None else target_forecast["predicted_water_level_m"]
            inflow = inflow if inflow is not None else target_forecast["last_known_inflow_ktcmd"]
            rainfall = rainfall if rainfall is not None else target_forecast["last_known_rainfall_mm"]
            forecast_source = source_name
        else:
            df = get_clean_dataset()
            last = df.iloc[-1]
            water_level = water_level if water_level is not None else float(last["water_level_m"])
            inflow = inflow if inflow is not None else float(last["inflow_ktcmd"])
            rainfall = rainfall if rainfall is not None else float(last["rainfall_mm"])
            forecast_source = "dataset_latest"

    if water_level is None or inflow is None or rainfall is None:
        raise HTTPException(status_code=400, detail="Provide water_level_m, inflow_ktcmd and rainfall_mm_24h, "
                                                      "or run a forecast first.")

    risk_map = generate_zone_risk_map(water_level, inflow, rainfall, req.resolution)
    if forecast_source:
        risk_map["forecast_source"] = forecast_source
    state.latest_risk_map = risk_map
    return risk_map


@router.get("/risk/zones")
def get_risk_zones():
    if state.latest_risk_map is None:
        raise HTTPException(status_code=404, detail="No risk map generated yet. Call POST /api/risk/generate first.")
    return state.latest_risk_map
