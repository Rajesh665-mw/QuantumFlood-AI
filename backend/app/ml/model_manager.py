"""
Persists and loads the trained ClassicalForecastingEngine so predictions can
be served without retraining on every request. Uses:
  - joblib for the sklearn model objects (binary, fast)
  - JSON for the ForecastResult metadata (human-readable, survives restarts)

On startup, if a persisted model + result exist on disk, they are
automatically restored — /api/forecast/results works immediately after
backend restart without retraining.
"""
import json
import logging
import joblib
from pathlib import Path
from dataclasses import asdict
from app.config.settings import MODEL_DIR
from app.ml.forecasting_engine import ClassicalForecastingEngine, ForecastResult
from app.quantum.qml_forecaster import QuantumVariationalRegressor
from app.quantum.qml_result import QmlForecastResult

logger = logging.getLogger(__name__)

MODEL_PATH = MODEL_DIR / "classical_forecasting_engine.joblib"
RESULT_PATH = MODEL_DIR / "forecast_result.json"

QML_MODEL_PATH = MODEL_DIR / "qml_forecasting_engine.joblib"
QML_RESULT_PATH = MODEL_DIR / "qml_forecast_result.json"


class ModelManager:
    _engine: ClassicalForecastingEngine = None
    _last_result: ForecastResult = None
    _qml_regressor: QuantumVariationalRegressor = None
    _last_qml_result: QmlForecastResult = None

    @classmethod
    def set_trained(cls, engine: ClassicalForecastingEngine, result: ForecastResult):
        cls._engine = engine
        cls._last_result = result
        # Persist model to disk
        joblib.dump(engine, MODEL_PATH)
        # Persist result metadata to disk as JSON
        try:
            with open(RESULT_PATH, "w") as f:
                json.dump(asdict(result), f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to persist ForecastResult: %s", e)

    @classmethod
    def get_engine(cls) -> ClassicalForecastingEngine:
        if cls._engine is None and MODEL_PATH.exists():
            try:
                cls._engine = joblib.load(MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load persisted model: %s", e)
        return cls._engine

    @classmethod
    def get_last_result(cls) -> ForecastResult:
        if cls._last_result is None and RESULT_PATH.exists():
            try:
                with open(RESULT_PATH, "r") as f:
                    data = json.load(f)
                cls._last_result = ForecastResult(**data)
            except Exception as e:
                logger.warning("Failed to load persisted ForecastResult: %s", e)
        return cls._last_result

    @classmethod
    def is_trained(cls) -> bool:
        return cls.get_engine() is not None

    # --- QML Forecaster Management ---

    @classmethod
    def set_qml_trained(cls, regressor: QuantumVariationalRegressor, result: QmlForecastResult):
        cls._qml_regressor = regressor
        cls._last_qml_result = result
        try:
            joblib.dump(regressor, QML_MODEL_PATH)
        except Exception as e:
            logger.warning("Failed to persist QML regressor to disk: %s", e)
        try:
            with open(QML_RESULT_PATH, "w") as f:
                json.dump(asdict(result), f, indent=2, default=str)
        except Exception as e:
            logger.warning("Failed to persist QmlForecastResult: %s", e)

    @classmethod
    def get_qml_regressor(cls) -> QuantumVariationalRegressor:
        if cls._qml_regressor is None and QML_MODEL_PATH.exists():
            try:
                cls._qml_regressor = joblib.load(QML_MODEL_PATH)
            except Exception as e:
                logger.warning("Failed to load persisted QML regressor: %s", e)
        return cls._qml_regressor

    @classmethod
    def get_last_qml_result(cls) -> QmlForecastResult:
        if cls._last_qml_result is None and QML_RESULT_PATH.exists():
            try:
                with open(QML_RESULT_PATH, "r") as f:
                    data = json.load(f)
                cls._last_qml_result = QmlForecastResult(**data)
            except Exception as e:
                logger.warning("Failed to load persisted QmlForecastResult: %s", e)
        return cls._last_qml_result

    @classmethod
    def is_qml_trained(cls) -> bool:
        return cls.get_qml_regressor() is not None

