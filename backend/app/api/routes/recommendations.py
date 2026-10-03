from fastapi import APIRouter, HTTPException
from app.services.pipeline_state import state

router = APIRouter()


@router.get("/recommendations")
def get_recommendations():
    if state.latest_recommendations is None:
        raise HTTPException(status_code=404, detail="No recommendations yet. Run optimisation first "
                                                      "(POST /api/optimization/run).")
    return state.latest_recommendations
