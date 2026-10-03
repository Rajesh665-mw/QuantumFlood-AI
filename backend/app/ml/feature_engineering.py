"""
Builds lag / rolling features for chronological forecasting. No shuffling,
no future information leaks into past rows.
"""
import pandas as pd

LAG_DAYS = [1, 2, 3, 7]
ROLLING_WINDOWS = [3, 7]


def build_features(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    df = df.copy()

    for lag in LAG_DAYS:
        df[f"rainfall_lag{lag}"] = df["rainfall_mm"].shift(lag)
        df[f"inflow_lag{lag}"] = df["inflow_ktcmd"].shift(lag)
        df[f"water_level_lag{lag}"] = df["water_level_m"].shift(lag)

    for w in ROLLING_WINDOWS:
        df[f"rainfall_roll{w}"] = df["rainfall_mm"].shift(1).rolling(w).mean()
        df[f"inflow_roll{w}"] = df["inflow_ktcmd"].shift(1).rolling(w).mean()

    df["day_of_year"] = df["date"].dt.dayofyear
    df["month"] = df["date"].dt.month

    df = df.dropna().reset_index(drop=True)

    feature_cols = [c for c in df.columns if c not in ("date", "data_source", target_col)]
    return df, feature_cols


def get_feature_target_frames(df: pd.DataFrame, target_col: str):
    engineered, feature_cols = build_features(df, target_col)
    X = engineered[feature_cols]
    y = engineered[target_col]
    dates = engineered["date"]
    return X, y, dates, feature_cols


def get_inference_features(df: pd.DataFrame, exclude_col: str):
    """Like get_feature_target_frames but for inference time, when the
    (future) target column does not exist in the input frame at all."""
    engineered, feature_cols = build_features(df, exclude_col)
    X = engineered[feature_cols]
    dates = engineered["date"]
    return X, dates, feature_cols
