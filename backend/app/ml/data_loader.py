"""
Loads the hydro-meteorological dataset (demo or real) and performs basic
structural validation before it enters the ML pipeline.
"""
import pandas as pd
from pathlib import Path
from app.config.settings import DATA_RAW_DIR

REQUIRED_COLUMNS = ["date", "rainfall_mm", "inflow_ktcmd", "water_level_m"]
DEFAULT_DEMO_FILE = DATA_RAW_DIR / "krishna_hydro_demo.csv"


class DataValidationError(Exception):
    pass


def load_hydro_dataset(path: Path = DEFAULT_DEMO_FILE) -> pd.DataFrame:
    if not path.exists():
        raise DataValidationError(
            f"Dataset not found at {path}. Run app/data/generate_demo_data.py "
            "to create the DEMO dataset, or point to a real dataset."
        )
    df = pd.read_csv(path)
    validate_schema(df)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def validate_schema(df: pd.DataFrame) -> None:
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        raise DataValidationError(f"Missing required columns: {missing_cols}")
    if df.empty:
        raise DataValidationError("Dataset is empty.")


def summarize_dataset(df: pd.DataFrame) -> dict:
    """Used by GET /api/data/summary - real computed stats, no fabrication."""
    numeric_cols = ["rainfall_mm", "inflow_ktcmd", "water_level_m"]
    missing_counts = {c: int(df[c].isna().sum()) for c in df.columns}
    duplicate_rows = int(df.duplicated().sum())

    return {
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "date_range": {
            "start": df["date"].min().strftime("%Y-%m-%d"),
            "end": df["date"].max().strftime("%Y-%m-%d"),
        },
        "missing_values": missing_counts,
        "duplicate_rows": duplicate_rows,
        "numeric_summary": {
            col: {
                "min": float(df[col].min()),
                "max": float(df[col].max()),
                "mean": round(float(df[col].mean()), 3),
                "std": round(float(df[col].std()), 3),
            }
            for col in numeric_cols
        },
        "data_source_label": df["data_source"].iloc[0] if "data_source" in df.columns else "UNKNOWN",
    }
