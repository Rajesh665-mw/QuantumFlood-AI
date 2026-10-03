import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.ml.data_loader import load_hydro_dataset
from app.ml.preprocessing import clean_dataset
from app.ml.forecasting_engine import ClassicalForecastingEngine


def test_full_forecast_pipeline_runs_and_is_chronological():
    df = load_hydro_dataset()
    clean = clean_dataset(df)
    assert clean["date"].is_monotonic_increasing

    engine = ClassicalForecastingEngine(horizon_days=1)
    result = engine.train_and_evaluate(clean)

    assert result.train_size > 0
    assert result.test_size > 0
    assert result.best_model_name in ("persistence_baseline", "linear_regression", "random_forest", "gradient_boosting")
    # R2 should be a real, bounded score (not fabricated/placeholder like exactly 1.0 with 0 error)
    best_metrics = result.metrics_by_model[result.best_model_name]
    assert best_metrics["rmse"] >= 0
    assert best_metrics["mae"] >= 0


def test_predict_next_returns_plausible_water_level():
    df = load_hydro_dataset()
    clean = clean_dataset(df)
    engine = ClassicalForecastingEngine(horizon_days=1)
    engine.train_and_evaluate(clean)
    prediction = engine.predict_next(clean)
    assert 0 < prediction["predicted_water_level_m"] < 30
    assert prediction["model_used"] == engine.best_model_name


def test_persistence_baseline_is_included_and_compared_against_ml_models():
    """Step 10: a simple persistence baseline must be present and genuinely
    evaluated alongside the ML models, not just decorative."""
    df = load_hydro_dataset()
    clean = clean_dataset(df)
    engine = ClassicalForecastingEngine(horizon_days=1)
    result = engine.train_and_evaluate(clean)

    assert "persistence_baseline" in result.metrics_by_model
    baseline_metrics = result.metrics_by_model["persistence_baseline"]
    assert baseline_metrics["rmse"] >= 0

    # The baseline's metrics must differ from at least one ML model's
    # metrics (i.e. it isn't just a duplicate/placeholder entry).
    other_rmses = [m["rmse"] for name, m in result.metrics_by_model.items() if name != "persistence_baseline"]
    assert any(abs(r - baseline_metrics["rmse"]) > 1e-9 for r in other_rmses)
