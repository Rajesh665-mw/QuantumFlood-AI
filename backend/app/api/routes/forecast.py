from fastapi import APIRouter, HTTPException
from dataclasses import asdict
import logging

from app.schemas.schemas import (
    ForecastTrainRequest,
    ForecastPredictRequest,
    QmlForecastTrainRequest,
    QmlForecastPredictRequest,
    ForecastCompareRequest,
)
from app.services.data_service import get_clean_dataset
from app.ml.forecasting_engine import ClassicalForecastingEngine
from app.ml.model_manager import ModelManager
from app.services.pipeline_state import state
from app.quantum.qml_config import QmlConfig
from app.quantum.qml_forecaster import (
    train_and_evaluate_qml,
    predict_next_qml,
    evaluate_qml_multiseed,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/forecast/train")
def train_forecast(req: ForecastTrainRequest):
    df = get_clean_dataset()
    if len(df) < 60:
        raise HTTPException(status_code=400, detail="Not enough data to train (need at least 60 rows).")

    engine = ClassicalForecastingEngine(horizon_days=req.horizon_days)
    result = engine.train_and_evaluate(df)
    ModelManager.set_trained(engine, result)

    return {
        "engine_type": result.engine_type,
        "best_model_name": result.best_model_name,
        "metrics_by_model": result.metrics_by_model,
        "train_size": result.train_size,
        "test_size": result.test_size,
        "horizon_days": result.horizon_days,
        "feature_columns": result.feature_columns,
    }


@router.post("/forecast/predict")
def predict_forecast(req: ForecastPredictRequest):
    engine = ModelManager.get_engine()
    if engine is None:
        raise HTTPException(status_code=400, detail="No trained model available. Call /api/forecast/train first.")

    if engine.horizon_days != req.horizon_days:
        # Retrain quickly for the requested horizon to keep the demo simple
        df = get_clean_dataset()
        engine = ClassicalForecastingEngine(horizon_days=req.horizon_days)
        result = engine.train_and_evaluate(df)
        ModelManager.set_trained(engine, result)

    df = get_clean_dataset()
    prediction = engine.predict_next(df)
    state.latest_forecast = prediction
    return prediction


@router.get("/forecast/results")
def get_forecast_results():
    result = ModelManager.get_last_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No forecast results yet. Train a model first.")
    return {
        "engine_type": result.engine_type,
        "best_model_name": result.best_model_name,
        "metrics_by_model": result.metrics_by_model,
        "predictions": result.predictions,
        "horizon_days": result.horizon_days,
        "train_size": result.train_size,
        "test_size": result.test_size,
        "latest_prediction": state.latest_forecast,
    }


# =====================================================================
# QML FORECASTING ENDPOINTS (UC-067 EXPERIMENTAL MODULE)
# =====================================================================

@router.post("/forecast/qml/train")
def train_qml_forecast(req: QmlForecastTrainRequest):
    df = get_clean_dataset()
    if len(df) < 60:
        raise HTTPException(status_code=400, detail="Not enough data to train (need at least 60 rows).")

    config = QmlConfig(
        n_qubits=4,
        n_layers=req.n_layers,
        max_iter=req.max_iter,
        train_subsample=req.train_subsample,
        seed=req.seed,
    )
    try:
        regressor, result = train_and_evaluate_qml(
            df=df,
            horizon_days=req.horizon_days,
            config=config,
        )
        ModelManager.set_qml_trained(regressor, result)
        return result.to_dict()
    except Exception as e:
        logger.exception("QML training error: %s", e)
        raise HTTPException(status_code=500, detail=f"QML training failed: {str(e)}")


@router.post("/forecast/qml/predict")
def predict_qml_forecast(req: QmlForecastPredictRequest):
    regressor = ModelManager.get_qml_regressor()
    df = get_clean_dataset()

    if regressor is None or regressor.horizon_days != req.horizon_days:
        # Retrain QML model with default parameters
        config = QmlConfig(n_qubits=4, n_layers=2, max_iter=30, train_subsample=100)
        try:
            regressor, result = train_and_evaluate_qml(df=df, horizon_days=req.horizon_days, config=config)
            ModelManager.set_qml_trained(regressor, result)
        except Exception as e:
            logger.exception("QML on-demand retraining error: %s", e)
            raise HTTPException(status_code=500, detail=f"QML model execution failed: {str(e)}")

    try:
        prediction = predict_next_qml(regressor, df)
        state.latest_qml_forecast = prediction
        return prediction
    except Exception as e:
        logger.exception("QML prediction error: %s", e)
        raise HTTPException(status_code=500, detail=f"QML prediction failed: {str(e)}")


@router.get("/forecast/qml/results")
def get_qml_forecast_results():
    result = ModelManager.get_last_qml_result()
    if result is None:
        raise HTTPException(status_code=404, detail="No QML forecast results yet. Call POST /api/forecast/qml/train first.")
    data = result.to_dict()
    data["latest_prediction"] = state.latest_qml_forecast
    return data


@router.post("/forecast/compare")
def compare_forecast(req: ForecastCompareRequest):
    """
    Tournament comparison between classical production models and QML VQR.
    Ensures QML failure isolation: classical results always succeed even if QML fails.
    """
    df = get_clean_dataset()

    # 1. Classical baseline
    c_engine = ModelManager.get_engine()
    c_result = ModelManager.get_last_result()
    if c_engine is None or c_engine.horizon_days != req.horizon_days or c_result is None:
        c_engine = ClassicalForecastingEngine(horizon_days=req.horizon_days)
        c_result = c_engine.train_and_evaluate(df)
        ModelManager.set_trained(c_engine, c_result)

    c_pred = state.latest_forecast
    if c_pred is None or c_pred.get("horizon_days") != req.horizon_days:
        c_pred = c_engine.predict_next(df)
        state.latest_forecast = c_pred

    best_classical_name = c_result.best_model_name
    best_classical_metrics = c_result.metrics_by_model.get(best_classical_name, {})

    classical_summary = {
        "model_name": best_classical_name,
        "metrics": best_classical_metrics,
        "predicted_water_level_m": c_pred.get("predicted_water_level_m"),
        "all_classical_models": c_result.metrics_by_model,
        "feature_columns": c_result.feature_columns,
    }

    # 2. QML model (with failure isolation)
    qml_summary = {
        "available": False,
        "error": None,
        "model_name": "Variational Quantum Regressor (VQR)",
        "metrics": None,
        "predicted_water_level_m": None,
        "training_time_s": None,
        "inference_time_s": None,
        "n_qubits": 4,
        "circuit_depth": 11,
        "n_parameters": 16,
        "simulator": "pure_numpy_statevector",
    }

    try:
        q_regressor = ModelManager.get_qml_regressor()
        q_result = ModelManager.get_last_qml_result()
        if q_regressor is None or q_regressor.horizon_days != req.horizon_days or q_result is None:
            config = QmlConfig(n_qubits=4, n_layers=2, max_iter=30, train_subsample=100)
            q_regressor, q_result = train_and_evaluate_qml(df=df, horizon_days=req.horizon_days, config=config)
            ModelManager.set_qml_trained(q_regressor, q_result)

        q_pred = state.latest_qml_forecast
        if q_pred is None or q_pred.get("horizon_days") != req.horizon_days:
            q_pred = predict_next_qml(q_regressor, df)
            state.latest_qml_forecast = q_pred

        qml_summary.update({
            "available": True,
            "metrics": {
                "mae": q_result.test_mae,
                "rmse": q_result.test_rmse,
                "r2": q_result.test_r2,
            },
            "predicted_water_level_m": q_pred.get("predicted_water_level_m"),
            "training_time_s": q_result.training_time_s,
            "inference_time_s": q_result.inference_time_s,
            "n_qubits": q_result.n_qubits,
            "circuit_depth": q_result.circuit_depth,
            "n_parameters": q_result.n_parameters,
            "simulator": q_result.simulator,
            "features_used": q_result.feature_names,
        })
    except Exception as e:
        logger.warning("QML comparison execution failed (isolated): %s", e)
        qml_summary["error"] = str(e)

    # 3. Objective comparison summary
    comparison_summary = {
        "horizon_days": req.horizon_days,
        "classical": classical_summary,
        "qml": qml_summary,
    }

    if qml_summary["available"]:
        c_rmse = best_classical_metrics.get("rmse", float("inf"))
        q_rmse = qml_summary["metrics"]["rmse"]
        c_mae = best_classical_metrics.get("mae", float("inf"))
        q_mae = qml_summary["metrics"]["mae"]

        if q_rmse < c_rmse:
            best_model = "Variational Quantum Regressor (VQR)"
            diff_text = f"QML RMSE is {round(c_rmse - q_rmse, 3)}m lower than best classical ({best_classical_name})."
        else:
            best_model = f"Classical {best_classical_name}"
            diff_text = f"Classical ({best_classical_name}) RMSE is {round(q_rmse - c_rmse, 3)}m lower than QML VQR."

        # Target B: Multi-seed statistical evaluation
        try:
            multiseed_res = evaluate_qml_multiseed(
                df=df,
                horizon_days=req.horizon_days,
                seeds=[42, 123, 777, 2026],
                max_iter=25,
                train_subsample=100,
            )
            comparison_summary["multiseed_evaluation"] = multiseed_res
        except Exception as e:
            logger.warning("Multi-seed QML evaluation skipped: %s", e)
            comparison_summary["multiseed_evaluation"] = None

        comparison_summary["comparison"] = {
            "lower_rmse_model": best_model,
            "rmse_difference_m": round(abs(q_rmse - c_rmse), 4),
            "mae_difference_m": round(abs(q_mae - c_mae), 4),
            "observation": diff_text,
            "scientific_note": (
                "Classical gradient boosting / tree ensembles remain the verified production baseline. "
                "The 4-qubit VQR demonstrates functional parameterized quantum regression via local statevector "
                "simulation without empirical quantum advantage claims."
            ),
        }

    return comparison_summary


@router.get("/forecast/qml/multiseed")
def get_qml_multiseed(horizon_days: int = 1):
    """
    Executes a multi-seed evaluation of the 4-qubit VQR across seeds [42, 123, 777, 2026]
    to demonstrate deterministic repeatability and statistical variance without cherry-picking.
    """
    df = get_clean_dataset()
    try:
        results = evaluate_qml_multiseed(
            df=df,
            horizon_days=horizon_days,
            seeds=[42, 123, 777, 2026],
            max_iter=30,
            train_subsample=100,
        )
        return results
    except Exception as e:
        logger.error("Failed multi-seed evaluation: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


