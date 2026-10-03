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
    return df.to_dict(orient="records")
