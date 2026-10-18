from fastapi import APIRouter, HTTPException
from app.schemas.schemas import RiskGenerateRequest
from app.risk.risk_engine import generate_zone_risk_map
from app.services.pipeline_state import state
from app.services.data_service import get_clean_dataset
from app.config.settings import ENABLE_LEGACY_SHARED_STATE
from app.services.study_area_service import resolve_study_area_context
from app.services.analysis_store import analysis_store

router = APIRouter()


@router.post("/risk/generate")
def generate_risk(req: RiskGenerateRequest):
    water_level = req.water_level_m
    inflow = req.inflow_ktcmd
    rainfall = req.rainfall_mm_24h

    aid = req.analysis_id
    bundle = None
    if aid:
        if not analysis_store.is_valid_id(aid):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(aid)
    else:
        aid = analysis_store.generate_id()

    forecast_source = None
    if req.use_latest_forecast and (water_level is None or inflow is None or rainfall is None):
        target_forecast = None
        source_name = None

        # Check request-scoped bundle first
        if bundle:
            if req.forecast_model_preference == "qml" and "qml_forecast" in bundle:
                target_forecast = bundle["qml_forecast"]
                source_name = "analysis_qml"
            elif "forecast" in bundle:
                target_forecast = bundle["forecast"]
                source_name = "analysis_classical"

        # Only fall back to ambient shared state if legacy mode is enabled or unscoped request
        if target_forecast is None and (ENABLE_LEGACY_SHARED_STATE or not req.analysis_id):
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
            water_level = water_level if water_level is not None else target_forecast.get("predicted_water_level_m")
            inflow = inflow if inflow is not None else target_forecast.get("last_known_inflow_ktcmd")
            rainfall = rainfall if rainfall is not None else target_forecast.get("last_known_rainfall_mm")
            forecast_source = source_name
        else:
            df = get_clean_dataset()
            last = df.iloc[-1]
            water_level = water_level if water_level is not None else float(last["water_level_m"])
            inflow = inflow if inflow is not None else float(last["inflow_ktcmd"])
            rainfall = rainfall if rainfall is not None else float(last["rainfall_mm"])
            forecast_source = "dataset_latest"

    if water_level is None or inflow is None or rainfall is None:
        raise HTTPException(
            status_code=400,
            detail="Provide water_level_m, inflow_ktcmd, and rainfall_mm_24h, or run a forecast for this analysis first."
        )

    study_area_payload = req.study_area
    if not study_area_payload and bundle and "study_area" in bundle:
        study_area_ctx = bundle["study_area"]
    else:
        try:
            is_benchmark = (
                req.use_benchmark is True
                or (study_area_payload is None and bundle is None and not req.analysis_id)
            )
            study_area_ctx = resolve_study_area_context(
                study_area_payload=study_area_payload,
                use_benchmark=is_benchmark,
                allow_fallback=ENABLE_LEGACY_SHARED_STATE or is_benchmark,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    risk_map = generate_zone_risk_map(water_level, inflow, rainfall, req.resolution, study_area=study_area_ctx)
    if forecast_source:
        risk_map["forecast_source"] = forecast_source
    risk_map["study_area"] = study_area_ctx
    risk_map["analysis_id"] = aid

    # Persist in isolated analysis store
    analysis_store.save(aid, {
        "analysis_id": aid,
        "study_area": study_area_ctx,
        "risk_map": risk_map,
        "scenario_params": {
            "water_level_m": water_level,
            "inflow_ktcmd": inflow,
            "rainfall_mm_24h": rainfall,
            "resolution": req.resolution,
        },
    })

    if ENABLE_LEGACY_SHARED_STATE:
        state.latest_risk_map = risk_map

    return risk_map


@router.get("/risk/zones")
def get_risk_zones(analysis_id: str = None):
    if analysis_id is not None:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle or "risk_map" not in bundle:
            raise HTTPException(status_code=404, detail=f"No risk map found for analysis '{analysis_id}'.")
        return bundle["risk_map"]

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(
            status_code=400,
            detail="Missing 'analysis_id' query parameter in multi-user mode."
        )

    if state.latest_risk_map is None:
        raise HTTPException(status_code=404, detail="No risk map generated yet. Call POST /api/risk/generate first.")
    return state.latest_risk_map
