from fastapi import APIRouter
from app.config.settings import STUDY_AREA

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "system": "QuantumFlood AI", "phase": "Quantum-Enhanced Flood Decision Support"}


@router.get("/regions")
def get_regions():
    return {"regions": [STUDY_AREA]}
