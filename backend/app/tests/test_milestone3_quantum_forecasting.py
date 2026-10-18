"""
Milestone 3 — Quantum Forecasting & Uncertainty Verification
============================================================
Validates:
1. Strict chronological training/test split isolation (zero future leakage).
2. Parameterized Quantum Circuit (PQC) 4-qubit VQR training and convergence.
3. Calibrated 95% uncertainty intervals (confidence_lower <= predicted <= confidence_upper).
4. Prediction live inference with uncertainty standard deviation.
5. API endpoints (/api/forecast/qml/predict and /api/forecast/compare) with failure isolation.
"""
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.quantum.qml_config import QmlConfig
from app.quantum.qml_forecaster import (
    train_and_evaluate_qml,
    predict_next_qml,
    prepare_qml_data,
)
from app.services.data_service import get_clean_dataset


@pytest.fixture
def test_client():
    return TestClient(app)


def test_chronological_data_isolation():
    """Verify that train and test splits are split strictly by date with zero leakage."""
    df = get_clean_dataset()
    X_train, X_test, y_train, y_test, dates_train, dates_test = prepare_qml_data(df, horizon_days=1, test_fraction=0.2)

    # Train dates must strictly precede test dates
    assert pd.to_datetime(dates_train.iloc[-1]) < pd.to_datetime(dates_test.iloc[0])
    assert len(X_train) + len(X_test) == len(dates_train) + len(dates_test)
    assert not X_train.isnull().any().any()
    assert not X_test.isnull().any().any()


def test_vqr_training_and_calibrated_uncertainty():
    """Verify that VQR trains, computes residual std, and generates valid confidence intervals."""
    df = get_clean_dataset()
    cfg = QmlConfig(n_qubits=4, layers=2, max_iter=15, train_subsample=60, seed=42)
    model, result = train_and_evaluate_qml(df, horizon_days=1, config=cfg)

    assert model.is_fitted is True
    assert model.residual_std > 0.0
    assert result.residual_std > 0.0
    assert result.uncertainty_calibrated is True

    # Check test predictions contain confidence bounds
    assert len(result.predictions) > 0
    for p in result.predictions[:5]:
        assert "confidence_lower" in p
        assert "confidence_upper" in p
        assert p["confidence_lower"] <= p["predicted"] <= p["confidence_upper"]


def test_predict_next_qml_uncertainty_interval():
    """Verify that predict_next_qml generates a forward prediction with calibrated 95% bounds."""
    df = get_clean_dataset()
    cfg = QmlConfig(n_qubits=4, layers=2, max_iter=15, train_subsample=60, seed=42)
    model, _ = train_and_evaluate_qml(df, horizon_days=1, config=cfg)

    pred = predict_next_qml(model, df, horizon_days=1)
    assert "predicted_water_level_m" in pred
    assert "confidence_lower_m" in pred
    assert "confidence_upper_m" in pred
    assert "uncertainty_std_m" in pred
    assert pred["confidence_lower_m"] <= pred["predicted_water_level_m"] <= pred["confidence_upper_m"]
    assert pred["uncertainty_std_m"] > 0.0
    assert pred["forecast_status"] == "LIVE_INFERENCE"


def test_api_qml_forecast_predict_endpoint(test_client):
    """Verify that /api/forecast/qml/predict returns calibrated confidence bounds."""
    res = test_client.post("/api/forecast/qml/predict", json={"horizon_days": 1})
    assert res.status_code == 200
    data = res.json()
    assert "predicted_water_level_m" in data
    assert "confidence_lower_m" in data
    assert "confidence_upper_m" in data
    assert data["confidence_lower_m"] <= data["predicted_water_level_m"] <= data["confidence_upper_m"]


def test_api_forecast_compare_with_uncertainty(test_client):
    """Verify that /api/forecast/compare returns both classical and QML metrics with uncertainty."""
    res = test_client.post("/api/forecast/compare", json={"horizon_days": 1})
    assert res.status_code == 200
    data = res.json()
    assert "classical" in data
    assert "qml" in data
    if data["qml"]["available"]:
        assert "confidence_lower_m" in data["qml"]
        assert "confidence_upper_m" in data["qml"]
        assert data["qml"]["uncertainty_calibrated"] is True
