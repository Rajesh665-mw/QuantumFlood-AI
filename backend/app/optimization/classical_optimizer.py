"""
ClassicalOptimizationEngine
=============================
Solves the sensor-placement problem as a WEIGHTED MAXIMUM COVERAGE problem:

  Given N candidate locations, a coverage radius, and a budget of K sensors,
  select the subset of size <= K that maximises the sum of risk weights of
  covered zones (each zone counted once even if covered by multiple
  sensors), with CRITICAL zones counted at an extra multiplier.

Algorithm: classic greedy set-cover approximation.
  At each step, pick the candidate that adds the largest MARGINAL increase
  in weighted coverage (i.e. covering zones not yet covered by any
  previously selected sensor). Repeat until K sensors are selected or no
  candidate adds further coverage.

This is the standard (1 - 1/e) ≈ 63% optimality-guaranteed greedy
algorithm for the NP-hard Maximum Coverage problem - a well-established
classical approach, chosen over an exact ILP solver for simplicity and
speed in this student prototype, while still being provably near-optimal.

Phase-2 hook: a future `QuantumOptimizationEngine` implementing the same
`optimize(candidates, zones, radius_km, num_sensors) -> OptimizationResult`
signature can be swapped in without changing API routes.
"""
from dataclasses import dataclass
from app.utils.geo_math import haversine_km
from app.config.settings import DEFAULT_CRITICAL_WEIGHT_MULTIPLIER


@dataclass
class OptimizationResult:
    engine_type: str
    selected_sensors: list
    coverage_percentage: float
    weighted_risk_coverage: float
    total_weighted_risk: float
    critical_zone_coverage_percentage: float
    covered_zone_ids: list
    uncovered_priority_zone_ids: list
    num_candidates_considered: int
    num_sensors_requested: int
    num_sensors_selected: int
    coverage_per_sensor: float = 0.0
    minimal_sensors_for_max_coverage: int = 0


def _compute_zone_weights(zones: list) -> dict:
    """Objective weight per zone: risk_score, boosted for CRITICAL zones."""
    zone_weight = {}
    for z in zones:
        w = float(z.get("risk_score", 1.0))
        if z.get("risk_level") == "CRITICAL":
            w *= DEFAULT_CRITICAL_WEIGHT_MULTIPLIER
        zone_weight[z["zone_id"]] = w
    return zone_weight


def _compute_candidate_coverage(candidates: list, zones: list, radius_km: float) -> dict:
    """candidate_id -> set of zone_ids within radius_km (real haversine distance)."""
    candidate_coverage = {}
    for c in candidates:
        covered = []
        for z in zones:
            if haversine_km(c["lat"], c["lon"], z["centroid"]["lat"], z["centroid"]["lon"]) <= radius_km:
                covered.append(z["zone_id"])
        candidate_coverage[c["candidate_id"]] = set(covered)
    return candidate_coverage


def _build_result(engine_type, candidates, zones, zone_weight, candidate_coverage,
                   selected_ids, radius_km, num_sensors) -> OptimizationResult:
    """Shared result-assembly logic for any candidate-selection strategy,
    given the final list of selected candidate_ids."""
    candidate_lookup = {c["candidate_id"]: c for c in candidates}
    covered_so_far = set()
    for cid in selected_ids:
        covered_so_far |= candidate_coverage[cid]

    selected_full = [
        {**candidate_lookup[cid], "covered_zone_ids": sorted(candidate_coverage[cid])}
        for cid in selected_ids
    ]

    all_zone_ids = {z["zone_id"] for z in zones}
    uncovered_zone_ids = all_zone_ids - covered_so_far
    critical_zone_ids = {z["zone_id"] for z in zones if z.get("risk_level") == "CRITICAL"}
    covered_critical = critical_zone_ids & covered_so_far

    weighted_risk_coverage = sum(zone_weight[z] for z in covered_so_far)
    total_weighted_risk = sum(zone_weight.values())
    coverage_pct = (len(covered_so_far) / len(all_zone_ids) * 100) if all_zone_ids else 0.0
    critical_pct = (len(covered_critical) / len(critical_zone_ids) * 100) if critical_zone_ids else 100.0

    uncovered_priority = sorted(uncovered_zone_ids, key=lambda zid: zone_weight[zid], reverse=True)

    # Determine minimal number of sensors that achieves this exact final coverage set
    cum_covered = set()
    min_sensors = len(selected_ids)
    for idx, cid in enumerate(selected_ids):
        cum_covered |= candidate_coverage[cid]
        if cum_covered == covered_so_far and idx + 1 < min_sensors:
            min_sensors = idx + 1
            break

    cov_per_sensor = round(weighted_risk_coverage / max(1, len(selected_full)), 2)

    return OptimizationResult(
        engine_type=engine_type,
        selected_sensors=selected_full,
        coverage_percentage=round(coverage_pct, 2),
        weighted_risk_coverage=round(weighted_risk_coverage, 2),
        total_weighted_risk=round(total_weighted_risk, 2),
        critical_zone_coverage_percentage=round(critical_pct, 2),
        covered_zone_ids=sorted(covered_so_far),
        uncovered_priority_zone_ids=uncovered_priority,
        num_candidates_considered=len(candidates),
        num_sensors_requested=num_sensors,
        num_sensors_selected=len(selected_full),
        coverage_per_sensor=cov_per_sensor,
        minimal_sensors_for_max_coverage=min_sensors,
    )


class ClassicalOptimizationEngine:
    """Approach A: greedy weighted maximum-coverage (see module docstring)."""

    engine_type = "classical_greedy"

    def optimize(self, candidates: list, zones: list, radius_km: float, num_sensors: int) -> OptimizationResult:
        zone_weight = _compute_zone_weights(zones)
        candidate_coverage = _compute_candidate_coverage(candidates, zones, radius_km)

        selected_ids = []
        covered_so_far = set()
        remaining = {c["candidate_id"]: c for c in candidates}

        for _ in range(min(num_sensors, len(candidates))):
            best_id, best_gain, best_new_zones = None, -1.0, set()
            for cid, cand in remaining.items():
                new_zones = candidate_coverage[cid] - covered_so_far
                gain = sum(zone_weight[z] for z in new_zones)
                if gain > best_gain:
                    best_id, best_gain, best_new_zones = cid, gain, new_zones
            if best_id is None or best_gain <= 0:
                break  # no more marginal coverage available
            selected_ids.append(best_id)
            covered_so_far |= best_new_zones
            del remaining[best_id]

        return _build_result(self.engine_type, candidates, zones, zone_weight,
                              candidate_coverage, selected_ids, radius_km, num_sensors)


class NaiveTopKOptimizer:
    """
    Approach B (Step 13 classical baseline comparison): a simpler, naive
    deterministic heuristic that ranks each candidate ONLY by its own
    individual weighted coverage (ignoring overlap with other selected
    candidates) and takes the top `num_sensors`. This typically
    UNDER-performs the greedy marginal-gain approach (Approach A) once
    candidates' coverage areas start to overlap, which is exactly the
    scientific point of including it: it gives an honest baseline showing
    the greedy algorithm's real, measurable advantage rather than just
    asserting it.
    """

    engine_type = "classical_naive_topk"

    def optimize(self, candidates: list, zones: list, radius_km: float, num_sensors: int) -> OptimizationResult:
        zone_weight = _compute_zone_weights(zones)
        candidate_coverage = _compute_candidate_coverage(candidates, zones, radius_km)

        individual_score = {
            c["candidate_id"]: sum(zone_weight[z] for z in candidate_coverage[c["candidate_id"]])
            for c in candidates
        }
        ranked_ids = sorted(individual_score, key=lambda cid: individual_score[cid], reverse=True)
        selected_ids = ranked_ids[:min(num_sensors, len(candidates))]

        return _build_result(self.engine_type, candidates, zones, zone_weight,
                              candidate_coverage, selected_ids, radius_km, num_sensors)
