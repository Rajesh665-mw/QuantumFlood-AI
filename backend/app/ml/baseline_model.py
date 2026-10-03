"""
PersistenceBaselineModel
==========================
The simplest possible forecasting baseline: predict that tomorrow's value
equals today's value ("naive persistence" / "no-change" forecast). This is
the standard scientific baseline used to check whether a more sophisticated
ML model actually earns its complexity - if the ML models can't beat this,
they aren't adding real forecasting value.

Implements the same fit/predict interface as scikit-learn estimators so it
drops directly into the existing CANDIDATE_MODELS comparison loop with no
special-casing required.
"""


class PersistenceBaselineModel:
    """Predicts water_level_m(t+horizon) = water_level_m(t). Requires the
    feature frame to include the current-day 'water_level_m' column, which
    ClassicalForecastingEngine's feature set always does (see
    forecasting_engine.py - only the *shifted* target column is excluded)."""

    def fit(self, X, y):
        # Stateless / deterministic - nothing to learn.
        return self

    def predict(self, X):
        if "water_level_m" not in X.columns:
            raise ValueError("PersistenceBaselineModel requires a 'water_level_m' feature column.")
        return X["water_level_m"].to_numpy()
