from fastapi import APIRouter
from app.services.pipeline_state import state
from app.config.settings import STUDY_AREA

router = APIRouter()


@router.get("/dashboard/summary")
def dashboard_summary():
    return {
        "study_area": STUDY_AREA,
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
