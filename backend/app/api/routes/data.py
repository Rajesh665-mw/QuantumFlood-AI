from fastapi import APIRouter, HTTPException
from app.services.data_service import (
    get_dataset_summary, get_raw_dataset, get_historical_flood_events, get_real_historical_flood_events,
)
from app.ml.data_loader import DataValidationError
from app.config.settings import DATA_PROVENANCE, RISK_ZONE_RESOLUTIONS

router = APIRouter()


@router.get("/datasets")
def list_datasets():
    return {
        "datasets": [
            {
                "id": "krishna_hydro_demo",
                "name": "Krishna Hydro-Meteorological Series (Simulated)",
                "mode": "SIMULATED_INPUT",
                "description": "Deterministic synthetic daily rainfall/inflow/water-level series "
                                "for the Vijayawada-Krishna study area.",
            },
            {
                "id": "historical_flood_events_demo",
                "name": "Historical Flood Events (Illustrative Sample)",
                "mode": "SIMULATED_INPUT",
                "description": "Small illustrative sample of flood-event-shaped records, not sourced "
                                "from an official archive.",
            },
            {
                "id": "historical_flood_events_real",
                "name": "Historical Flood Events (Real / Sourced)",
                "mode": "REAL_HISTORICAL",
                "description": "Documented flood events at Prakasam Barrage / Vijayawada (1903, 1998, "
                                "2009, 2024), sourced from published news and scientific reporting. "
                                "A small, citable sample - not a complete authoritative CWC archive.",
            },
        ]
    }


@router.get("/data/summary")
def data_summary():
    try:
        return get_dataset_summary()
    except DataValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/data/timeseries")
def data_timeseries(limit: int = 180):
    try:
        df = get_raw_dataset().tail(limit)
        return {"records": df.assign(date=df["date"].astype(str)).to_dict(orient="records")}
    except DataValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/data/historical-events")
def historical_events():
    """DEMO/illustrative events - kept for backward compatibility."""
    return {"events": get_historical_flood_events()}


@router.get("/data/historical-events-real")
def historical_events_real():
    """REAL_HISTORICAL, sourced flood events - see each record's `citation` field."""
    return {"events": get_real_historical_flood_events()}


@router.get("/data/provenance")
def data_provenance():
    """
    Step 15: single endpoint the frontend's Data & Analytics / Data
    Provenance section reads to show, per data category, whether it is
    REAL_HISTORICAL, SIMULATED_INPUT, PARTIALLY_REAL, PROJECT_DEFINED, or MODELLED_SPATIAL - and why.
    """
    return {
        "provenance": DATA_PROVENANCE,
        "risk_zone_resolutions": RISK_ZONE_RESOLUTIONS,
    }
