"""
Pipeline State — in-memory + disk-backed persistence.

Holds the latest results of each pipeline stage (forecast -> risk ->
optimisation -> connectivity -> recommendations) so pages like the Command
Center can display the current system state without re-running every module
on every GET request.

Persistence layer: meaningful outputs (forecast, risk map, optimisation
params, optimisation/connectivity results) are serialised to JSON files
under data/processed/pipeline/ on every write, and automatically restored
on process startup. This fixes the audit finding that a server restart
previously wiped all computed state.

Only COMPUTED PIPELINE OUTPUTS are persisted — temporary UI-only state and
in-memory model objects are not (those are handled by model_manager.py).
"""
import json
import logging
import threading
from dataclasses import asdict, is_dataclass
from pathlib import Path
from app.config.settings import DATA_PROCESSED_DIR

logger = logging.getLogger(__name__)

PIPELINE_DIR = DATA_PROCESSED_DIR / "pipeline"
PIPELINE_DIR.mkdir(parents=True, exist_ok=True)

# Module-level lock protects all pipeline state writes (JSON serialisation
# to disk) from interleaving under concurrent FastAPI/uvicorn requests.
_state_lock = threading.Lock()

_FILE_MAP = {
    "latest_forecast": PIPELINE_DIR / "latest_forecast.json",
    "latest_qml_forecast": PIPELINE_DIR / "latest_qml_forecast.json",
    "latest_risk_map": PIPELINE_DIR / "latest_risk_map.json",
    "latest_optimization": PIPELINE_DIR / "latest_optimization.json",
    "latest_connectivity": PIPELINE_DIR / "latest_connectivity.json",
    "latest_recommendations": PIPELINE_DIR / "latest_recommendations.json",
    "optimization_params": PIPELINE_DIR / "optimization_params.json",
    "latest_safe_locations": PIPELINE_DIR / "latest_safe_locations.json",
    "latest_evacuation_routes": PIPELINE_DIR / "latest_evacuation_routes.json",
    "latest_adaptive_redeployments": PIPELINE_DIR / "latest_adaptive_redeployments.json",
    "latest_resilience": PIPELINE_DIR / "latest_resilience.json",
    "latest_resource_allocations": PIPELINE_DIR / "latest_resource_allocations.json",
    "active_scenario": PIPELINE_DIR / "active_scenario.json",
}


def _save(key: str, value):
    """Persist a pipeline artifact to disk as JSON (thread-safe)."""
    path = _FILE_MAP.get(key)
    if path is None or value is None:
        return
    try:
        serializable = asdict(value) if is_dataclass(value) else value
        with _state_lock:
            with open(path, "w") as f:
                json.dump(serializable, f, indent=2, default=str)
    except Exception as e:
        logger.warning("Failed to persist pipeline state '%s': %s", key, e)


def _load(key: str):
    """Load a previously persisted pipeline artifact from disk."""
    path = _FILE_MAP.get(key)
    if path is None or not path.exists():
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load persisted pipeline state '%s': %s", key, e)
        return None


class PipelineState:
    """Singleton-style state holder with transparent disk persistence."""

    def __init__(self):
        # Restore from disk on construction (= process startup)
        self._latest_forecast: dict = _load("latest_forecast")
        self._latest_qml_forecast: dict = _load("latest_qml_forecast")
        self._latest_risk_map: dict = _load("latest_risk_map")
        self._latest_optimization: dict = _load("latest_optimization")
        self._latest_connectivity: dict = _load("latest_connectivity")
        self._latest_recommendations: dict = _load("latest_recommendations")
        self._optimization_params: dict = _load("optimization_params")
        self._latest_safe_locations: dict = _load("latest_safe_locations")
        self._latest_evacuation_routes: dict = _load("latest_evacuation_routes")
        self._latest_adaptive_redeployments: dict = _load("latest_adaptive_redeployments")
        self._latest_resilience: dict = _load("latest_resilience")
        self._latest_resource_allocations: dict = _load("latest_resource_allocations")
        self._active_scenario: dict = _load("active_scenario")

        loaded = [k for k in _FILE_MAP if getattr(self, f"_{k}") is not None]
        if loaded:
            logger.info("Restored persisted pipeline state: %s", ", ".join(loaded))

    # --- latest_forecast ---
    @property
    def latest_forecast(self):
        return self._latest_forecast

    @latest_forecast.setter
    def latest_forecast(self, value):
        self._latest_forecast = value
        _save("latest_forecast", value)

    # --- latest_qml_forecast ---
    @property
    def latest_qml_forecast(self):
        return self._latest_qml_forecast

    @latest_qml_forecast.setter
    def latest_qml_forecast(self, value):
        self._latest_qml_forecast = value
        _save("latest_qml_forecast", value)

    # --- latest_risk_map ---
    @property
    def latest_risk_map(self):
        return self._latest_risk_map

    @latest_risk_map.setter
    def latest_risk_map(self, value):
        self._latest_risk_map = value
        _save("latest_risk_map", value)

    # --- latest_optimization ---
    @property
    def latest_optimization(self):
        return self._latest_optimization

    @latest_optimization.setter
    def latest_optimization(self, value):
        self._latest_optimization = value
        _save("latest_optimization", value)

    # --- latest_connectivity ---
    @property
    def latest_connectivity(self):
        return self._latest_connectivity

    @latest_connectivity.setter
    def latest_connectivity(self, value):
        self._latest_connectivity = value
        _save("latest_connectivity", value)

    # --- latest_recommendations ---
    @property
    def latest_recommendations(self):
        return self._latest_recommendations

    @latest_recommendations.setter
    def latest_recommendations(self, value):
        self._latest_recommendations = value
        _save("latest_recommendations", value)

    # --- optimization_params ---
    @property
    def optimization_params(self):
        return self._optimization_params

    @optimization_params.setter
    def optimization_params(self, value):
        self._optimization_params = value
        _save("optimization_params", value)

    # --- latest_safe_locations ---
    @property
    def latest_safe_locations(self):
        return self._latest_safe_locations

    @latest_safe_locations.setter
    def latest_safe_locations(self, value):
        self._latest_safe_locations = value
        _save("latest_safe_locations", value)

    # --- latest_evacuation_routes ---
    @property
    def latest_evacuation_routes(self):
        return self._latest_evacuation_routes

    @latest_evacuation_routes.setter
    def latest_evacuation_routes(self, value):
        self._latest_evacuation_routes = value
        _save("latest_evacuation_routes", value)

    # --- latest_adaptive_redeployments ---
    @property
    def latest_adaptive_redeployments(self):
        return self._latest_adaptive_redeployments

    @latest_adaptive_redeployments.setter
    def latest_adaptive_redeployments(self, value):
        self._latest_adaptive_redeployments = value
        _save("latest_adaptive_redeployments", value)

    # --- latest_resilience ---
    @property
    def latest_resilience(self):
        return self._latest_resilience

    @latest_resilience.setter
    def latest_resilience(self, value):
        self._latest_resilience = value
        _save("latest_resilience", value)

    # --- latest_resource_allocations ---
    @property
    def latest_resource_allocations(self):
        return self._latest_resource_allocations

    @latest_resource_allocations.setter
    def latest_resource_allocations(self, value):
        self._latest_resource_allocations = value
        _save("latest_resource_allocations", value)

    # --- active_scenario ---
    @property
    def active_scenario(self):
        return self._active_scenario

    @active_scenario.setter
    def active_scenario(self, value):
        self._active_scenario = value
        _save("active_scenario", value)


state = PipelineState()

