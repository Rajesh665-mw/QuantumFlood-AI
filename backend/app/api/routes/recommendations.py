from typing import Optional
from fastapi import APIRouter, HTTPException
from app.services.pipeline_state import state
from app.services.analysis_store import analysis_store
from app.config.settings import ENABLE_LEGACY_SHARED_STATE

router = APIRouter()


@router.get("/recommendations")
def get_recommendations(analysis_id: Optional[str] = None):
    if analysis_id:
        if not analysis_store.is_valid_id(analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis session '{analysis_id}' not found.")
        recs = bundle.get("recommendations")
        if recs is None:
            raise HTTPException(status_code=404, detail=f"No recommendations in analysis session '{analysis_id}'. Run POST /api/optimization/run with analysis_id first.")
        return recs

    if not ENABLE_LEGACY_SHARED_STATE:
        raise HTTPException(status_code=400, detail="Missing 'analysis_id' query parameter in multi-user mode.")

    if state.latest_recommendations is None:
        raise HTTPException(status_code=404, detail="No recommendations yet. Run optimisation first (POST /api/optimization/run).")
    return state.latest_recommendations
