"""
Emergency Resource Allocation Service
=====================================
Optimally allocates limited user-specified emergency disaster response resources
(Rescue Teams, Medical Units, Relief Units, Emergency Vehicles) across
vulnerable zones in the study area.

Mathematical Formulation (Quantum-Ready Multi-Resource Integer Knapsack):
  Given resources R = {Rescue, Medical, Relief, Vehicles} with budgets B_r,
  and zones Z with computed Priority Scores P_z.

  Decision variables:
    x_zr in {0, 1, ..., M_zr} (number of units of resource r assigned to zone z)

  Objective:
    max sum_{z in Z} sum_{r in R} [ U_r * P_z * log(1 + x_zr) ]

  Subject to:
    sum_{z in Z} x_zr <= B_r            forall r in R   (Resource budget constraints)
    x_zr <= M_zr                        forall z, r     (Zone operational capacity caps)
    x_zr = 0                            forall z with risk == LOW (Eligibility constraint)

  Classical Solver:
    Deterministic marginal-utility greedy knapsack allocation with priority ranking.
  Quantum-Ready:
    Expressible as QUBO via binary expansion of integer variables x_zr = sum_{b} 2^b * q_zrb.

Scientific Honesty Policy:
  - Does NOT invent or assert real government stockpile figures.
  - Quantities are strictly user-configured scenario parameters.
"""
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

RESOURCE_TYPES = {
    "rescue_teams": {"label": "Rescue Teams", "unit": "teams", "priority_weight": 1.4, "max_per_zone": 2},
    "medical_teams": {"label": "Medical Teams", "unit": "units", "priority_weight": 1.2, "max_per_zone": 2},
    "relief_units": {"label": "Relief Supply Units", "unit": "units", "priority_weight": 1.0, "max_per_zone": 2},
    "emergency_vehicles": {"label": "Emergency Vehicles", "unit": "vehicles", "priority_weight": 1.1, "max_per_zone": 3},
}


def _calculate_zone_priority(zone: Dict[str, Any]) -> float:
    """Computes a transparent priority score for a zone based on risk and river proximity."""
    risk_score = zone.get("risk_score", 1)
    dist_river = zone.get("distance_to_river_km", 5.0)
    risk_level = zone.get("risk_level", "LOW")

    # Base risk score (1 - 4)
    p = float(risk_score) * 2.0

    # Critical booster
    if risk_level == "CRITICAL":
        p += 3.0
    elif risk_level == "HIGH":
        p += 1.5

    # River proximity booster (closer to river -> higher urgent vulnerability)
    proximity_booster = max(0.0, 3.0 - (dist_river / 1.5))
    p += proximity_booster

    return round(p, 2)


def allocate_emergency_resources(
    zones: List[Dict[str, Any]],
    rescue_teams: int = 5,
    medical_teams: int = 3,
    relief_units: int = 4,
    emergency_vehicles: int = 4,
    min_risk_level: str = "MODERATE"
) -> Dict[str, Any]:
    """
    Executes constrained resource allocation across eligible zones.
    """
    budgets = {
        "rescue_teams": max(0, rescue_teams),
        "medical_teams": max(0, medical_teams),
        "relief_units": max(0, relief_units),
        "emergency_vehicles": max(0, emergency_vehicles),
    }

    # Filter eligible zones (exclude LOW by default)
    risk_order = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}
    min_rank = risk_order.get(min_risk_level, 2)

    eligible_zones = []
    for z in zones:
        lvl = z.get("risk_level", "LOW")
        if risk_order.get(lvl, 1) >= min_rank:
            p_score = _calculate_zone_priority(z)
            eligible_zones.append({
                **z,
                "priority_score": p_score,
                "allocated": {r: 0 for r in budgets}
            })

    # Sort eligible zones by priority score descending
    eligible_zones.sort(key=lambda x: x["priority_score"], reverse=True)

    # Allocate resources using marginal-utility greedy knapsack:
    # At each step, allocate one unit to the (zone, resource) pair with the
    # highest marginal utility gain: U_r * P_z * [log(1 + x_zr + 1) - log(1 + x_zr)].
    # This correctly implements the documented diminishing-returns objective
    # max sum_{z,r} U_r * P_z * log(1 + x_zr), subject to budget and per-zone caps.
    import math

    remaining_budgets = dict(budgets)

    # Pre-compute all possible (zone, resource) marginal utilities and greedily
    # pick the best allocation at each step until all budgets are exhausted.
    while True:
        best_gain = -1.0
        best_zone = None
        best_resource = None

        for r_type, config in RESOURCE_TYPES.items():
            if remaining_budgets[r_type] <= 0:
                continue
            max_per_z = config["max_per_zone"]
            u_r = config["priority_weight"]

            for z in eligible_zones:
                current_alloc = z["allocated"][r_type]
                if current_alloc >= max_per_z:
                    continue

                p_z = z["priority_score"]
                # Marginal utility: U_r * P_z * [log(1 + x + 1) - log(1 + x)]
                marginal_gain = u_r * p_z * (math.log(2 + current_alloc) - math.log(1 + current_alloc))

                if marginal_gain > best_gain:
                    best_gain = marginal_gain
                    best_zone = z
                    best_resource = r_type

        if best_zone is None or best_gain <= 0:
            break

        best_zone["allocated"][best_resource] += 1
        remaining_budgets[best_resource] -= 1

    # Assemble explanations and return model
    zone_results = []
    total_assigned = {r: budgets[r] - remaining_budgets[r] for r in budgets}

    for z in eligible_zones:
        alloc = z["allocated"]
        if sum(alloc.values()) > 0:
            alloc_str = ", ".join([f"{count} {RESOURCE_TYPES[r]['label']}" for r, count in alloc.items() if count > 0])
            explanation = (
                f"Zone {z['zone_id']} assigned {alloc_str} based on {z['risk_level']} flood risk "
                f"(Priority Score: {z['priority_score']}) and {z['distance_to_river_km']} km standoff from river channel."
            )

            zone_results.append({
                "zone_id": z["zone_id"],
                "risk_level": z["risk_level"],
                "risk_score": z["risk_score"],
                "distance_to_river_km": z["distance_to_river_km"],
                "centroid": z["centroid"],
                "priority_score": z["priority_score"],
                "allocated_resources": alloc,
                "total_units_allocated": sum(alloc.values()),
                "explanation": explanation
            })

    return {
        "status": "SUCCESS",
        "parameters": {
            "requested_budgets": budgets,
            "min_risk_level": min_risk_level
        },
        "summary": {
            "eligible_zones_count": len(eligible_zones),
            "zones_serviced_count": len(zone_results),
            "allocated_quantities": total_assigned,
            "unallocated_quantities": remaining_budgets,
            "budget_exhaustion_pct": {
                r: round((total_assigned[r] / budgets[r] * 100.0) if budgets[r] > 0 else 100.0, 1)
                for r in budgets
            }
        },
        "allocations": zone_results,
        "mathematical_formulation": {
            "objective": "Maximize Priority-Weighted Utility sum(U_r * P_z * log(1 + x_zr))",
            "decision_variables": "x_zr in {0, 1, ..., M_zr} integer units",
            "constraints": [
                "Sum over zones <= Available Resource Budget",
                "Per-zone allocation <= Zone Operational Capacity",
                "Allocation prohibited in unimpacted/LOW risk zones"
            ],
            "quantum_readiness": "Formulated as Bounded Integer Knapsack / QUBO-convertible binary problem."
        },
        "scientific_honesty_note": (
            "Resource quantities are user-configured simulation inputs. "
            "This model represents classical operational decision support; it does not "
            "represent active emergency deployment orders."
        )
    }
