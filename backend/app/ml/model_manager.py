"""
Persists and loads the trained ClassicalForecastingEngine so predictions can
be served without retraining on every request. Uses:
  - joblib for the sklearn model objects (binary, fast)
  - JSON for the ForecastResult metadata (human-readable, survives restarts)

On startup, if a persisted model + result exist on disk, they are
automatically restored — /api/forecast/results works immediately after
backend restart without retraining.
"""
import os
import uuid
import json
import logging
import threading
import joblib
from pathlib import Path
from typing import Optional, Dict
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


def _atomic_joblib_dump(obj, path: Path):
    """Atomically dumps a python object with joblib using a process-unique temp file."""
    nonce = uuid.uuid4().hex[:8]
    tmp_path = path.with_suffix(f".tmp_{os.getpid()}_{threading.get_ident()}_{nonce}")
    try:
        joblib.dump(obj, tmp_path)
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning("Failed atomic joblib dump to '%s': %s", path, e)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def _atomic_json_dump(data_dict: dict, path: Path):
    """Atomically dumps dict data to JSON using a process-unique temp file."""
    nonce = uuid.uuid4().hex[:8]
    tmp_path = path.with_suffix(f".tmp_{os.getpid()}_{threading.get_ident()}_{nonce}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        logger.warning("Failed atomic json dump to '%s': %s", path, e)
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


class ModelManager:
    _lock = threading.RLock()
    _engine: Optional[ClassicalForecastingEngine] = None
    _last_result: Optional[ForecastResult] = None
    _engines_by_horizon: Dict[int, ClassicalForecastingEngine] = {}
    _results_by_horizon: Dict[int, ForecastResult] = {}

    _qml_regressor: Optional[QuantumVariationalRegressor] = None
    _last_qml_result: Optional[QmlForecastResult] = None
    _qml_regressors_by_horizon: Dict[int, QuantumVariationalRegressor] = {}
    _qml_results_by_horizon: Dict[int, QmlForecastResult] = {}

    @classmethod
    def set_trained(cls, engine: ClassicalForecastingEngine, result: ForecastResult, persist_disk: bool = True):
        with cls._lock:
            cls._engine = engine
            cls._last_result = result
            cls._engines_by_horizon[engine.horizon_days] = engine
            cls._results_by_horizon[engine.horizon_days] = result

            if persist_disk:
                _atomic_joblib_dump(engine, MODEL_PATH)
                _atomic_json_dump(asdict(result), RESULT_PATH)

    @classmethod
    def get_engine(cls, horizon_days: Optional[int] = None) -> Optional[ClassicalForecastingEngine]:
        with cls._lock:
            if horizon_days is not None and horizon_days in cls._engines_by_horizon:
                return cls._engines_by_horizon[horizon_days]

            if cls._engine is None and MODEL_PATH.exists():
                try:
                    cls._engine = joblib.load(MODEL_PATH)
                    if cls._engine is not None:
                        cls._engines_by_horizon[cls._engine.horizon_days] = cls._engine
                except Exception as e:
                    logger.warning("Failed to load persisted model: %s", e)

            if horizon_days is not None:
                if cls._engine is not None and cls._engine.horizon_days == horizon_days:
                    return cls._engine
                return cls._engines_by_horizon.get(horizon_days)

            return cls._engine

    @classmethod
    def get_or_train_engine(cls, horizon_days: int, df) -> ClassicalForecastingEngine:
        """
        Thread-safe retrieval or on-demand training of forecasting engine for the given horizon.
        Prevents in-place mutation of baseline model files.
        """
        with cls._lock:
            existing = cls.get_engine(horizon_days=horizon_days)
            if existing is not None:
                return existing

            logger.info("Training isolated forecasting engine for horizon_days=%d", horizon_days)
            engine = ClassicalForecastingEngine(horizon_days=horizon_days)
            result = engine.train_and_evaluate(df)
            # Cache in memory; only persist to disk if no disk model exists
            persist_disk = not MODEL_PATH.exists()
            cls.set_trained(engine, result, persist_disk=persist_disk)
            return engine

    @classmethod
    def get_last_result(cls, horizon_days: Optional[int] = None) -> Optional[ForecastResult]:
        with cls._lock:
            if horizon_days is not None and horizon_days in cls._results_by_horizon:
                return cls._results_by_horizon[horizon_days]

            if cls._last_result is None and RESULT_PATH.exists():
                try:
                    with open(RESULT_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cls._last_result = ForecastResult(**data)
                    cls._results_by_horizon[cls._last_result.horizon_days] = cls._last_result
                except Exception as e:
                    logger.warning("Failed to load persisted ForecastResult: %s", e)

            if horizon_days is not None:
                if cls._last_result is not None and cls._last_result.horizon_days == horizon_days:
                    return cls._last_result
                return cls._results_by_horizon.get(horizon_days)

            return cls._last_result

    @classmethod
    def is_trained(cls) -> bool:
        return cls.get_engine() is not None

    # --- QML Forecaster Management ---

    @classmethod
    def set_qml_trained(cls, regressor: QuantumVariationalRegressor, result: QmlForecastResult, persist_disk: bool = True):
        with cls._lock:
            cls._qml_regressor = regressor
            cls._last_qml_result = result
            cls._qml_regressors_by_horizon[regressor.horizon_days] = regressor
            cls._qml_results_by_horizon[regressor.horizon_days] = result

            if persist_disk:
                _atomic_joblib_dump(regressor, QML_MODEL_PATH)
                _atomic_json_dump(asdict(result), QML_RESULT_PATH)

    @classmethod
    def get_qml_regressor(cls, horizon_days: Optional[int] = None) -> Optional[QuantumVariationalRegressor]:
        with cls._lock:
            if horizon_days is not None and horizon_days in cls._qml_regressors_by_horizon:
                return cls._qml_regressors_by_horizon[horizon_days]

            if cls._qml_regressor is None and QML_MODEL_PATH.exists():
                try:
                    cls._qml_regressor = joblib.load(QML_MODEL_PATH)
                    if cls._qml_regressor is not None:
                        cls._qml_regressors_by_horizon[cls._qml_regressor.horizon_days] = cls._qml_regressor
                except Exception as e:
                    logger.warning("Failed to load persisted QML regressor: %s", e)

            if horizon_days is not None:
                if cls._qml_regressor is not None and cls._qml_regressor.horizon_days == horizon_days:
                    return cls._qml_regressor
                return cls._qml_regressors_by_horizon.get(horizon_days)

            return cls._qml_regressor

    @classmethod
    def get_last_qml_result(cls, horizon_days: Optional[int] = None) -> Optional[QmlForecastResult]:
        with cls._lock:
            if horizon_days is not None and horizon_days in cls._qml_results_by_horizon:
                return cls._qml_results_by_horizon[horizon_days]

            if cls._last_qml_result is None and QML_RESULT_PATH.exists():
                try:
                    with open(QML_RESULT_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cls._last_qml_result = QmlForecastResult(**data)
                    cls._qml_results_by_horizon[cls._last_qml_result.horizon_days] = cls._last_qml_result
                except Exception as e:
                    logger.warning("Failed to load persisted QmlForecastResult: %s", e)

            if horizon_days is not None:
                if cls._last_qml_result is not None and cls._last_qml_result.horizon_days == horizon_days:
                    return cls._last_qml_result
                return cls._qml_results_by_horizon.get(horizon_days)

            return cls._last_qml_result

    @classmethod
    def is_qml_trained(cls) -> bool:
        return cls.get_qml_regressor() is not None

