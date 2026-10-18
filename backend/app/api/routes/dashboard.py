from typing import Optional
from fastapi import APIRouter, HTTPException
from app.services.pipeline_state import state
from app.services.study_area_service import get_current_study_area
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE, STUDY_AREA

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary(analysis_id: Optional[str] = None):
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        risk_map = bundle.get("risk_map")
        forecast = bundle.get("forecast")
        optimization = bundle.get("optimization")
        connectivity = bundle.get("connectivity")
        recommendations = bundle.get("recommendations")
        study_area = bundle.get("study_area") or STUDY_AREA
        return {
            "analysis_id": analysis_id,
            "study_area": study_area,
            "forecast_available": forecast is not None,
            "latest_forecast": forecast,
            "risk_available": risk_map is not None,
            "base_risk": risk_map["base_classification"] if risk_map else None,
            "critical_zone_count": risk_map.get("critical_zone_count") if risk_map else None,
            "high_zone_count": risk_map.get("high_zone_count") if risk_map else None,
            "optimization_available": optimization is not None,
            "optimization": optimization,
            "connectivity_available": connectivity is not None,
            "connectivity": connectivity,
            "recommendations": recommendations,
        }

    if not ENABLE_LEGACY_SHARED_STATE:
        return {
            "analysis_id": None,
            "study_area": STUDY_AREA,
            "forecast_available": False,
            "latest_forecast": None,
            "risk_available": False,
            "base_risk": None,
            "critical_zone_count": 0,
            "high_zone_count": 0,
            "optimization_available": False,
            "optimization": None,
            "connectivity_available": False,
            "connectivity": None,
            "recommendations": None,
        }

    return {
        "study_area": get_current_study_area(),
        "forecast_available": state.latest_forecast is not None,
        "latest_forecast": state.latest_forecast,
        "risk_available": state.latest_risk_map is not None,
        "base_risk": state.latest_risk_map["base_classification"] if state.latest_risk_map else None,
        "critical_zone_count": state.latest_risk_map["critical_zone_count"] if state.latest_risk_map else None,
        "high_zone_count": state.latest_risk_map["high_zone_count"] if state.latest_risk_map else None,
        "optimization_available": state.latest_optimization is not None,
        "optimization": state.latest_optimization,
        "connectivity_available": state.latest_connectivity is not None,
        "connectivity": state.latest_connectivity,
        "recommendations": state.latest_recommendations,
    }
