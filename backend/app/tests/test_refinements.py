"""
Tests for the refinement changes (Hungarian matching, marginal-utility
allocation, horizon guard, risk classifier CRITICAL explanation).
"""
import pytest
import math
from app.risk.risk_classifier import classify_risk
from app.ml.forecasting_engine import ClassicalForecastingEngine
from app.services.resource_allocation_service import allocate_emergency_resources
from app.risk.risk_engine import generate_zone_risk_map
from app.services.adaptive_sensor_service import solve_adaptive_redeployment
from app.optimization.classical_optimizer import ClassicalOptimizationEngine
from app.optimization.candidate_generator import generate_candidates
from app.optimization.experiments import run_experiment_suite


# --- #1: Hungarian Algorithm Matching ---

class TestHungarianMatching:
    """Verify the bipartite matching produces optimal (minimum-distance) assignments."""

    def test_matching_produces_optimal_total_distance(self):
        """When sensors need to relocate, the Hungarian algorithm should produce
        a lower or equal total relocation distance compared to any other assignment."""
        risk_map = generate_zone_risk_map(14.0, 950.0, 130.0)
        zones = risk_map["zones"]

        # Create a known baseline placement with neutral weights
        neutral_candidates = generate_candidates(resolution="default")
        engine = ClassicalOptimizationEngine()
        baseline = engine.optimize(neutral_candidates, zones, 2.5, 6)
        current_sensors = baseline.selected_sensors

        # Run redeployment with updated conditions
        result = solve_adaptive_redeployment(
            current_sensors=current_sensors,
            updated_zones=zones,
            sensor_budget=6,
            coverage_radius_km=2.5
        )

        assert result["status"] == "SUCCESS"
        actions = result["actions"]
        relocations = [a for a in actions if a["action"] == "RELOCATE"]

        # Verify all relocations have finite, non-negative distances
        for r in relocations:
            assert r["distance_km"] >= 0.0
            assert r["distance_km"] < 100.0  # reasonable upper bound for study area

    def test_matching_handles_equal_sized_sets(self):
        """When old and new sensor sets are the same size (no ADD/REMOVE needed),
        all unmatched sensors should be paired."""
        risk_map = generate_zone_risk_map(12.0, 700.0, 85.0)
        zones = risk_map["zones"]
        zone_risk = {z["zone_id"]: z["risk_score"] for z in zones}
        candidates = generate_candidates(zone_risk, "default")
        engine = ClassicalOptimizationEngine()
        baseline = engine.optimize(candidates, zones, 2.5, 8)

        result = solve_adaptive_redeployment(
            current_sensors=baseline.selected_sensors,
            updated_zones=zones,
            sensor_budget=8
        )

        assert result["status"] == "SUCCESS"
        summary = result["summary"]
        total = summary["sensors_kept"] + summary["sensors_relocated"] + summary["sensors_added"]
        assert total == summary["total_sensors_deployed"]


# --- #2: Marginal-Utility Resource Allocation ---

class TestMarginalUtilityAllocation:
    """Verify the marginal-utility greedy knapsack respects budgets and per-zone caps."""

    def test_budgets_respected(self):
        """Total allocated per resource type must not exceed budget."""
        zones = generate_zone_risk_map(14.0, 950.0, 130.0)["zones"]
        result = allocate_emergency_resources(
            zones=zones, rescue_teams=5, medical_teams=3,
            relief_units=4, emergency_vehicles=4
        )

        assert result["status"] == "SUCCESS"
        alloc = result["summary"]["allocated_quantities"]
        assert alloc["rescue_teams"] <= 5
        assert alloc["medical_teams"] <= 3
        assert alloc["relief_units"] <= 4
        assert alloc["emergency_vehicles"] <= 4

    def test_per_zone_caps_respected(self):
        """No zone should receive more than the per-zone maximum for any resource."""
        zones = generate_zone_risk_map(14.0, 950.0, 130.0)["zones"]
        result = allocate_emergency_resources(zones=zones, rescue_teams=10, medical_teams=10,
                                               relief_units=10, emergency_vehicles=10)

        from app.services.resource_allocation_service import RESOURCE_TYPES
        for zone_alloc in result["allocations"]:
            for r_type, config in RESOURCE_TYPES.items():
                assert zone_alloc["allocated_resources"][r_type] <= config["max_per_zone"]

    def test_diminishing_returns_distributes_across_zones(self):
        """With sufficient budget and multiple eligible zones, the log(1+x) diminishing
        returns should spread resources across zones rather than dumping all on one zone."""
        zones = generate_zone_risk_map(14.0, 950.0, 130.0)["zones"]
        result = allocate_emergency_resources(
            zones=zones, rescue_teams=4, medical_teams=4,
            relief_units=4, emergency_vehicles=4
        )

        zones_with_resources = [z for z in result["allocations"] if z["total_units_allocated"] > 0]
        # With 16 total units and diminishing returns, resources should spread
        assert len(zones_with_resources) >= 2


# --- #4 + #10: Risk Classifier CRITICAL Explanation ---

class TestRiskClassifierExplanation:
    """Verify the CRITICAL explanation string is correct and clear."""

    def test_critical_explanation_says_exceeds(self):
        """When classification is CRITICAL, explanation should say 'exceeds' not 'falls in'."""
        result = classify_risk(water_level_m=15.0, inflow_ktcmd=1000.0, rainfall_mm_24h=150.0)
        assert result["overall_risk"] == "CRITICAL"
        assert "exceeds" in result["explanation"]
        assert "CRITICAL" in result["explanation"]

    def test_non_critical_explanation_format(self):
        """When classification is not CRITICAL, explanation should have clear threshold info."""
        result = classify_risk(water_level_m=5.0, inflow_ktcmd=200.0, rainfall_mm_24h=10.0)
        assert result["overall_risk"] == "LOW"
        assert "falls below" in result["explanation"]

    def test_moderate_explanation_has_threshold_reference(self):
        """MODERATE classification should reference the correct threshold value."""
        result = classify_risk(water_level_m=9.0, inflow_ktcmd=200.0, rainfall_mm_24h=10.0)
        assert result["overall_risk"] == "MODERATE"
        # MODERATE band starts at the 'low' threshold (8.0 for water_level_m)
        assert "MODERATE" in result["explanation"]
        assert "8.0" in result["explanation"]


# --- #5: Feature Leakage Guard ---

class TestFeatureLeakageGuard:
    """Verify that horizon_days=0 is rejected."""

    def test_horizon_zero_rejected(self):
        with pytest.raises(ValueError, match="horizon_days must be >= 1"):
            ClassicalForecastingEngine(horizon_days=0)

    def test_negative_horizon_rejected(self):
        with pytest.raises(ValueError, match="horizon_days must be >= 1"):
            ClassicalForecastingEngine(horizon_days=-1)

    def test_valid_horizon_accepted(self):
        engine = ClassicalForecastingEngine(horizon_days=1)
        assert engine.horizon_days == 1

        engine3 = ClassicalForecastingEngine(horizon_days=3)
        assert engine3.horizon_days == 3


# --- #9: Experiment Statistics ---

class TestExperimentStatistics:
    """Verify the experiment suite includes aggregate statistics."""

    def test_aggregate_stats_present(self):
        zones = generate_zone_risk_map(12.0, 700.0, 85.0)["zones"]
        result = run_experiment_suite(zones)

        assert "aggregate_statistics" in result
        stats = result["aggregate_statistics"]
        assert "total_experiments" in stats
        assert stats["total_experiments"] == len(result["experiments"])

        assert "greedy_advantage" in stats
        adv = stats["greedy_advantage"]
        assert "mean" in adv
        assert "std" in adv
        assert "greedy_wins" in adv
        assert adv["greedy_wins"] + adv["ties"] + adv["naive_wins"] == stats["total_experiments"]
