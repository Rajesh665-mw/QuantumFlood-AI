"""
Adaptive Sensor Redeployment Service
====================================
Determines how existing deployed sensor stations should adapt, relocate, or be
supplemented when flood risk evolves across the study area.

Problem Formulation (Quantum-Ready Transition Optimization):
  Old deployment S_old, new candidate pool C, updated zone weights w_z.
  Decision variables:
    y_j in {0, 1} for j in C (1 if sensor placed at candidate j)
    m_ij in {0, 1} for i in S_old, j in C (1 if sensor i relocated to site j)
    c_z in {0, 1} (1 if zone z is covered)

  Objective:
    max [ sum_{z in Z} w_z * c_z ] - lambda * [ sum_{i in S_old, j in C} dist(i, j) * m_ij ]

  Constraints:
    sum_{j in C} y_j <= K                          (sensor budget constraint)
    c_z <= sum_{j in C: dist(j, z) <= R} y_j       (zone coverage definition)
    y_j = sum_{i} m_ij + a_j                       (site activation via relocation or addition)
    sum_{j} m_ij <= 1                              (each existing sensor relocated at most once)

   Classical Solver:
     1. Solves updated weighted maximum coverage for optimal target positions.
     2. Computes OPTIMAL minimum-distance bipartite matching (Hungarian algorithm /
        scipy.optimize.linear_sum_assignment) to map existing sensors to new target
        positions. This is a provably optimal O(n³) assignment — not a greedy heuristic.
     3. Categorizes actions into KEEP, RELOCATE, ADD, REMOVE with deterministic explanations.
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.optimization.classical_optimizer import ClassicalOptimizationEngine, OptimizationResult
from app.optimization.candidate_generator import generate_candidates
from app.utils.geo_math import haversine_km
from app.config.settings import DEFAULT_CRITICAL_WEIGHT_MULTIPLIER

logger = logging.getLogger(__name__)


def _compute_coverage_for_sensors(sensors: List[Dict[str, Any]], zones: List[Dict[str, Any]], radius_km: float):
    """Evaluates coverage of a specific sensor set against a zone risk map."""
    zone_lookup = {z["zone_id"]: z for z in zones}
    all_zone_ids = set(zone_lookup.keys())
    critical_zone_ids = {z["zone_id"] for z in zones if z.get("risk_level") == "CRITICAL"}

    covered = set()
    for s in sensors:
        s_lat, s_lon = s["lat"], s["lon"]
        for z in zones:
            c = z["centroid"]
            if haversine_km(s_lat, s_lon, c["lat"], c["lon"]) <= radius_km:
                covered.add(z["zone_id"])

    weighted_cov = 0.0
    total_weighted = 0.0
    for z in zones:
        zid = z["zone_id"]
        w = float(z.get("risk_score", 1))
        if z.get("risk_level") == "CRITICAL":
            w *= DEFAULT_CRITICAL_WEIGHT_MULTIPLIER
        total_weighted += w
        if zid in covered:
            weighted_cov += w

    cov_pct = (len(covered) / len(all_zone_ids) * 100.0) if all_zone_ids else 0.0
    crit_cov = covered & critical_zone_ids
    crit_pct = (len(crit_cov) / len(critical_zone_ids) * 100.0) if critical_zone_ids else 100.0

    return {
        "covered_zones": sorted(covered),
        "covered_count": len(covered),
        "total_zones": len(all_zone_ids),
        "coverage_percentage": round(cov_pct, 2),
        "critical_coverage_percentage": round(crit_pct, 2),
        "weighted_risk_coverage": round(weighted_cov, 2),
        "total_weighted_risk": round(total_weighted, 2),
    }


def solve_adaptive_redeployment(
    current_sensors: List[Dict[str, Any]],
    updated_zones: List[Dict[str, Any]],
    sensor_budget: int = 8,
    coverage_radius_km: float = 2.5,
    resolution: str = "default"
) -> Dict[str, Any]:
    """
    Compares current deployment against optimal deployment under the updated risk map,
    computing concrete redeployment actions and objective improvements.
    """
    zone_risk_lookup = {z["zone_id"]: z.get("risk_score", 1) for z in updated_zones}
    candidates = generate_candidates(zone_risk_lookup, resolution)

    # 1. Run optimization under the updated risk conditions
    engine = ClassicalOptimizationEngine()
    opt_result: OptimizationResult = engine.optimize(
        candidates, updated_zones, coverage_radius_km, sensor_budget
    )
    new_sensors = opt_result.selected_sensors

    # 2. Evaluate current sensors under the updated risk conditions
    baseline_eval = _compute_coverage_for_sensors(current_sensors, updated_zones, coverage_radius_km)

    # 3. Match old sensors to new sensors
    old_ids = {s["candidate_id"]: s for s in current_sensors}
    new_ids = {s["candidate_id"]: s for s in new_sensors}

    actions = []
    kept_ids = set()

    # Direct keeps (same candidate site selected in both)
    for cid in old_ids:
        if cid in new_ids:
            kept_ids.add(cid)
            old_s = old_ids[cid]
            actions.append({
                "action": "KEEP",
                "sensor_id": cid,
                "current_site": old_s,
                "target_site": old_s,
                "distance_km": 0.0,
                "reason": f"Site {cid} remains optimal under updated risk conditions. Preserves local monitoring continuity."
            })

    unmatched_old = [s for cid, s in old_ids.items() if cid not in kept_ids]
    unmatched_new = [s for cid, s in new_ids.items() if cid not in kept_ids]

    # Optimal minimum-distance bipartite matching using the Hungarian algorithm
    # (scipy.optimize.linear_sum_assignment). This guarantees a provably optimal
    # assignment that minimises total relocation distance — unlike the previous
    # greedy nearest-pair heuristic which could produce suboptimal pairings when
    # a globally cheaper assignment exists.
    matched_pairs = []
    rem_old = list(unmatched_old)
    rem_new = list(unmatched_new)

    if rem_old and rem_new:
        n_old, n_new = len(rem_old), len(rem_new)
        cost_matrix = np.zeros((n_old, n_new))
        for i, o in enumerate(rem_old):
            for j, n in enumerate(rem_new):
                cost_matrix[i, j] = haversine_km(o["lat"], o["lon"], n["lat"], n["lon"])

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matched_old_indices = set()
        matched_new_indices = set()

        for r, c in zip(row_ind, col_ind):
            matched_pairs.append((rem_old[r], rem_new[c], round(cost_matrix[r, c], 2)))
            matched_old_indices.add(r)
            matched_new_indices.add(c)

        # Remaining unmatched sensors (when sets differ in size)
        rem_old = [rem_old[i] for i in range(n_old) if i not in matched_old_indices]
        rem_new = [rem_new[j] for j in range(n_new) if j not in matched_new_indices]

    for old_s, new_s, dist in matched_pairs:
        new_covered = set(new_s.get("covered_zone_ids", []))
        critical_new_covered = [
            zid for zid in new_covered
            if any(z["zone_id"] == zid and z.get("risk_level") == "CRITICAL" for z in updated_zones)
        ]

        reason = (
            f"Relocate {old_s['candidate_id']} -> {new_s['candidate_id']} ({dist} km). "
            f"Expands coverage to newly critical/high-risk zones ({', '.join(critical_new_covered) if critical_new_covered else 'Zone ' + new_s.get('zone_id', '')})."
        )

        actions.append({
            "action": "RELOCATE",
            "sensor_id": old_s["candidate_id"],
            "current_site": old_s,
            "target_site": new_s,
            "distance_km": dist,
            "reason": reason
        })

    # Remaining new sites become ADD
    for new_s in rem_new:
        actions.append({
            "action": "ADD",
            "sensor_id": new_s["candidate_id"],
            "current_site": None,
            "target_site": new_s,
            "distance_km": 0.0,
            "reason": f"Deploy supplementary sensor to site {new_s['candidate_id']} within available budget."
        })

    # Remaining old sites become REMOVE
    for old_s in rem_old:
        actions.append({
            "action": "REMOVE",
            "sensor_id": old_s["candidate_id"],
            "current_site": old_s,
            "target_site": None,
            "distance_km": 0.0,
            "reason": f"Decommission sensor at {old_s['candidate_id']} as monitoring priority shifted away."
        })

    # Order actions: KEEP, RELOCATE, ADD, REMOVE
    order = {"KEEP": 1, "RELOCATE": 2, "ADD": 3, "REMOVE": 4}
    actions.sort(key=lambda a: order.get(a["action"], 99))

    # Metrics comparison
    weighted_diff = round(opt_result.weighted_risk_coverage - baseline_eval["weighted_risk_coverage"], 2)
    cov_pct_diff = round(opt_result.coverage_percentage - baseline_eval["coverage_percentage"], 2)
    crit_pct_diff = round(opt_result.critical_zone_coverage_percentage - baseline_eval["critical_coverage_percentage"], 2)
    sensors_moved = sum(1 for a in actions if a["action"] == "RELOCATE")

    return {
        "status": "SUCCESS",
        "actions": actions,
        "summary": {
            "total_sensors_deployed": len(new_sensors),
            "sensors_kept": sum(1 for a in actions if a["action"] == "KEEP"),
            "sensors_relocated": sensors_moved,
            "sensors_added": sum(1 for a in actions if a["action"] == "ADD"),
            "sensors_removed": sum(1 for a in actions if a["action"] == "REMOVE"),
            "baseline_coverage": baseline_eval,
            "updated_coverage": {
                "coverage_percentage": opt_result.coverage_percentage,
                "critical_coverage_percentage": opt_result.critical_zone_coverage_percentage,
                "weighted_risk_coverage": opt_result.weighted_risk_coverage,
                "total_weighted_risk": opt_result.total_weighted_risk,
                "covered_zones_count": len(opt_result.covered_zone_ids)
            },
            "improvements": {
                "weighted_risk_coverage_gain": weighted_diff,
                "coverage_percentage_gain": cov_pct_diff,
                "critical_coverage_percentage_gain": crit_pct_diff,
            }
        },
        "recommendation_narrative": (
            f"Adaptive redeployment recommends moving {sensors_moved} sensors, yielding a "
            f"+{weighted_diff} increase in weighted risk coverage and raising critical zone coverage "
            f"to {opt_result.critical_zone_coverage_percentage}% under the updated flood risk map."
        ),
        "target_optimization": asdict(opt_result)
    }
