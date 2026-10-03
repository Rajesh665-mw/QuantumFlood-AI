"""
ClassicalForecastingEngine
===========================
Real, modular classical ML forecasting pipeline for the hydrological
regression task (predicting water_level_m, N days ahead, from rainfall
and inflow history).

Architecture note (Quantum readiness):
This class implements the `ForecastEngine` interface informally (fit/predict/
evaluate + a common `ForecastResult` return shape). A future
`QuantumForecastingEngine` can be dropped in behind the same interface
without touching API routes or the frontend contract.
"""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

from app.ml.feature_engineering import get_feature_target_frames, get_inference_features
from app.ml.evaluation import evaluate_regression
from app.ml.baseline_model import PersistenceBaselineModel

TARGET_COL = "water_level_m"


@dataclass
class ForecastResult:
    engine_type: str  # "classical" (future: "quantum")
    best_model_name: str
    metrics_by_model: dict
    predictions: list  # list of {date, actual, predicted}
    feature_columns: list
    horizon_days: int
    train_size: int
    test_size: int


def _chronological_split(X, y, dates, test_fraction=0.2):
    n = len(X)
    split_idx = int(n * (1 - test_fraction))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    dates_train, dates_test = dates.iloc[:split_idx], dates.iloc[split_idx:]
    return X_train, X_test, y_train, y_test, dates_train, dates_test


CANDIDATE_MODELS = {
    "persistence_baseline": PersistenceBaselineModel(),
    "linear_regression": LinearRegression(),
    "random_forest": RandomForestRegressor(n_estimators=200, max_depth=8, random_state=42),
    "gradient_boosting": GradientBoostingRegressor(n_estimators=150, max_depth=3, random_state=42),
}


class ClassicalForecastingEngine:
    """engine_type = 'classical' — see module docstring for Phase-2 hook."""

    engine_type = "classical"

    def __init__(self, horizon_days: int = 1):
        if horizon_days < 1:
            raise ValueError(
                f"horizon_days must be >= 1 (got {horizon_days}). "
                "horizon_days=0 would constitute feature leakage because the current "
                "day's water_level_m is used as a feature to predict the target."
            )
        self.horizon_days = horizon_days
        self.models = {}
        self.best_model_name: Optional[str] = None
        self.feature_columns: list = []

    def train_and_evaluate(self, df: pd.DataFrame) -> ForecastResult:
        working = df.copy()
        shifted_target_col = TARGET_COL + "_target"
        # Shift target forward by horizon so features at day t predict water
        # level at day t+horizon (true forecasting, not same-day fitting).
        working[shifted_target_col] = working[TARGET_COL].shift(-self.horizon_days)
        working = working.dropna(subset=[shifted_target_col])

        # Exclude the shifted target itself from features (avoids leakage);
        # today's actual water_level_m remains a valid predictor.
        X, y, dates, feature_cols = get_feature_target_frames(working, shifted_target_col)
        self.feature_columns = feature_cols

        X_train, X_test, y_train, y_test, dates_train, dates_test = _chronological_split(X, y, dates)

        metrics_by_model = {}
        fitted_models = {}
        for name, model in CANDIDATE_MODELS.items():
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            metrics_by_model[name] = evaluate_regression(y_test, preds)
            fitted_models[name] = model

        # Select best model by lowest RMSE on the held-out chronological test set
        self.best_model_name = min(metrics_by_model, key=lambda m: metrics_by_model[m]["rmse"])
        self.models = fitted_models
        best_model = fitted_models[self.best_model_name]
        best_preds = best_model.predict(X_test)

        predictions = [
            {
                "date": pd.Timestamp(d).strftime("%Y-%m-%d"),
                "actual": round(float(a), 3),
                "predicted": round(float(p), 3),
            }
            for d, a, p in zip(dates_test, y_test, best_preds)
        ]

        return ForecastResult(
            engine_type=self.engine_type,
            best_model_name=self.best_model_name,
            metrics_by_model=metrics_by_model,
            predictions=predictions,
            feature_columns=feature_cols,
            horizon_days=self.horizon_days,
            train_size=len(X_train),
            test_size=len(X_test),
        )

    def predict_next(self, df: pd.DataFrame) -> dict:
        """Predicts water_level_m `horizon_days` ahead of the most recent
        available row, using the currently trained best model."""
        if not self.models or self.best_model_name is None:
            raise RuntimeError("Model must be trained before calling predict_next().")

        # Use the same exclusion column name as training (a shifted-target
        # column that doesn't exist here) so the feature set matches exactly.
        X, dates, _ = get_inference_features(df, TARGET_COL + "_target")
        latest_row = X.iloc[[-1]][self.feature_columns]
        model = self.models[self.best_model_name]
        prediction = float(model.predict(latest_row)[0])
        last_known = df.iloc[-1]

        return {
            "based_on_date": pd.Timestamp(dates.iloc[-1]).strftime("%Y-%m-%d"),
            "horizon_days": self.horizon_days,
            "predicted_water_level_m": round(prediction, 3),
            "last_known_rainfall_mm": round(float(last_known["rainfall_mm"]), 2),
            "last_known_inflow_ktcmd": round(float(last_known["inflow_ktcmd"]), 2),
            "last_known_water_level_m": round(float(last_known["water_level_m"]), 3),
            "model_used": self.best_model_name,
        }
