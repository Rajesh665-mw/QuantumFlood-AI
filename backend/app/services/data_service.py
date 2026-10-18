"""
Loads and cleans the hydro dataset once per process, caching the result in
memory. Wraps ml.data_loader + ml.preprocessing.
"""
import pandas as pd
from app.ml.data_loader import load_hydro_dataset, summarize_dataset
from app.ml.preprocessing import clean_dataset
from app.config.settings import DATA_RAW_DIR

_cached_clean_df: pd.DataFrame = None
_cached_raw_df: pd.DataFrame = None


def get_clean_dataset() -> pd.DataFrame:
    global _cached_clean_df, _cached_raw_df
    if _cached_clean_df is None:
        _cached_raw_df = load_hydro_dataset()
        _cached_clean_df = clean_dataset(_cached_raw_df)
    return _cached_clean_df


def get_raw_dataset() -> pd.DataFrame:
    global _cached_raw_df
    if _cached_raw_df is None:
        _cached_raw_df = load_hydro_dataset()
    return _cached_raw_df


def get_dataset_summary() -> dict:
    return summarize_dataset(get_raw_dataset())


def get_historical_flood_events() -> list:
    """DEMO/illustrative flood events - kept for uninterrupted demo-mode
    operation (see get_real_historical_flood_events for the sourced,
    REAL_HISTORICAL alternative)."""
    path = DATA_RAW_DIR / "historical_flood_events_demo.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    return df.to_dict(orient="records")


def get_real_historical_flood_events() -> list:
    """REAL_HISTORICAL flood events at Prakasam Barrage / Vijayawada, sourced
    from published news/scientific reporting - see
    app/data/generate_real_flood_events.py for per-record citations."""
    path = DATA_RAW_DIR / "historical_flood_events_real.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    df = df.astype(object).where(pd.notnull(df), None)
    records = df.to_dict(orient="records")

    enriched = []
    for r in records:
        peak_cusecs = r.get("peak_discharge_cusecs")
        year = r.get("year")

        if peak_cusecs is not None:
            if peak_cusecs >= 1100000:
                severity_class = "CATASTROPHIC"
                severity_calc = f"Discharge ({peak_cusecs:,.0f} cusecs) exceeded barrage design discharge (1.11M cusecs), causing widespread urban breach and inundation."
            elif peak_cusecs >= 800000:
                severity_class = "HIGH"
                severity_calc = f"Discharge ({peak_cusecs:,.0f} cusecs) exceeded 70% of barrage capacity; prompted major evacuation of low-lying riparian colonies."
            elif peak_cusecs >= 500000:
                severity_class = "MODERATE"
                severity_calc = f"Discharge ({peak_cusecs:,.0f} cusecs) surpassed second warning level (17.5 ft stage) at Prakasam Barrage."
            else:
                severity_class = "LOW"
                severity_calc = f"Discharge ({peak_cusecs:,.0f} cusecs) remained within first flood warning threshold."
        else:
            severity_class = "HISTORIC_BENCHMARK"
            severity_calc = "Pre-dam archival record: unquantified peak discharge, referenced as the historic benchmark prior to upstream reservoir construction."

        inundated_zones = ["Z-001", "Z-002", "Z-007", "Z-008", "Z-013", "Z-014"] if year in [2009, 2024] else ["Z-001", "Z-002"]
        sensor_relevance = (
            f"Sensors placed along near-river grid cells ({', '.join(inundated_zones[:4])}) provide critical early-warning coverage for high-inflow events matching the {year} hydrograph."
        )

        r["severity_class"] = severity_class
        r["severity_calculation_method"] = severity_calc
        r["inundated_risk_zones"] = inundated_zones
        r["sensor_placement_relevance"] = sensor_relevance
        enriched.append(r)

    return enriched
