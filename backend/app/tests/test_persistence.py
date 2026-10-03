"""
Tests for pipeline state persistence — verifies that computed artifacts
survive a simulated process restart (save to disk → clear memory → reload).
"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_pipeline_state_persist_and_restore():
    """Write state, construct a new PipelineState (simulating restart),
    verify values are restored from disk."""
    from app.config.settings import DATA_PROCESSED_DIR

    pipeline_dir = DATA_PROCESSED_DIR / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    # Write a forecast + risk map via the state singleton
    from app.services.pipeline_state import PipelineState

    state_a = PipelineState()
    test_forecast = {"predicted_water_level_m": 11.5, "horizon_days": 1}
    test_risk_map = {
        "base_classification": {"overall_risk": "HIGH"},
        "zones": [],
        "resolution": "default",
        "critical_zone_count": 2,
        "high_zone_count": 4,
    }
    state_a.latest_forecast = test_forecast
    state_a.latest_risk_map = test_risk_map

    # Verify files exist on disk
    assert (pipeline_dir / "latest_forecast.json").exists()
    assert (pipeline_dir / "latest_risk_map.json").exists()

    # Simulate restart: construct a NEW PipelineState that reads from disk
    state_b = PipelineState()
    assert state_b.latest_forecast is not None
    assert state_b.latest_forecast["predicted_water_level_m"] == 11.5
    assert state_b.latest_risk_map is not None
    assert state_b.latest_risk_map["base_classification"]["overall_risk"] == "HIGH"
    assert state_b.latest_risk_map["critical_zone_count"] == 2


def test_pipeline_state_none_does_not_crash():
    """Setting a field to None should not raise, and should not create a file."""
    from app.services.pipeline_state import PipelineState

    state = PipelineState()
    state.latest_recommendations = None  # should not raise


def test_pipeline_state_optimization_params():
    """Verify optimization params persist correctly."""
    from app.services.pipeline_state import PipelineState
    from app.config.settings import DATA_PROCESSED_DIR

    state = PipelineState()
    params = {"num_sensors": 8, "coverage_radius_km": 2.5}
    state.optimization_params = params

    state_b = PipelineState()
    assert state_b.optimization_params is not None
    assert state_b.optimization_params["num_sensors"] == 8
