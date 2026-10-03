"""
Cleans the validated dataset: handles missing values, duplicates, and
invalid rows before feature engineering.
"""
import pandas as pd


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Drop exact duplicate rows
    df = df.drop_duplicates()

    # Drop duplicate dates keeping the first (chronological) occurrence
    df = df.drop_duplicates(subset=["date"], keep="first")

    # Numeric columns: forward-fill then back-fill small gaps (documented
    # imputation strategy - never fabricated values, just gap interpolation)
    numeric_cols = ["rainfall_mm", "inflow_ktcmd", "water_level_m"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df[numeric_cols] = df[numeric_cols].interpolate(method="linear", limit_direction="both")

    # Drop rows that still have missing critical values after interpolation
    df = df.dropna(subset=numeric_cols)

    # Physically invalid values (e.g. negative rainfall) are clipped, not dropped
    df["rainfall_mm"] = df["rainfall_mm"].clip(lower=0)
    df["inflow_ktcmd"] = df["inflow_ktcmd"].clip(lower=0)
    df["water_level_m"] = df["water_level_m"].clip(lower=0)

    df = df.sort_values("date").reset_index(drop=True)
    return df
