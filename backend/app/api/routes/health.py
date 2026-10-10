from fastapi import APIRouter
from app.services.study_area_service import get_current_study_area

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "system": "QuantumFlood AI", "phase": "Quantum-Enhanced Flood Decision Support"}


@router.get("/regions")
def get_regions():
    return {"regions": [get_current_study_area()]}
