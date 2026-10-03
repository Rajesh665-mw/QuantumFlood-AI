"""
Quantum Optimization Engine
===========================
High-level service matching the ClassicalOptimizationEngine signature.
Integrates domain candidate and zone objects with the QAOA quantum optimization pipeline.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
import numpy as np

from app.optimization.classical_optimizer import OptimizationResult, _compute_zone_weights, _compute_candidate_coverage
from app.quantum.qaoa_solver import QaoaSolver
from app.quantum.quantum_config import QaoaConfig
from app.quantum.quantum_result import QuantumOptimizationResult
from app.optimization.qubo_builder import build_sensor_qubo_from_domain
from app.config.settings import DEFAULT_CRITICAL_WEIGHT_MULTIPLIER


class QuantumOptimizationEngine:
    """
    Quantum optimization engine implementing the same problem interface
    as ClassicalOptimizationEngine.
    """

    def __init__(self, solver: Optional[QaoaSolver] = None):
        self.solver = solver or QaoaSolver()

    def optimize(
        self,
        candidates: List[Dict[str, Any]],
        zones: List[Dict[str, Any]],
        coverage_radius_km: float,
        num_sensors: int,
        p: int = 1,
        shots: int = 1024,
        seed: Optional[int] = 42,
        formulation_mode: str = "pairwise",
    ) -> Tuple[OptimizationResult, QuantumOptimizationResult]:
        """
        Executes QAOA on the domain problem and packages the output into both:
        1. OptimizationResult (standard QuantumFlood pipeline format for seamless map/UI integration).
        2. QuantumOptimizationResult (rich quantum-specific diagnostics and execution metadata).
        """
        config = QaoaConfig(
            p=p,
            shots=shots,
            seed=seed,
            formulation_mode=formulation_mode,
        )

        # 1. Build QUBO from domain
        qubo_result = build_sensor_qubo_from_domain(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=coverage_radius_km,
            budget=num_sensors,
        )

        # 2. Extract coverage matrix and weights for independent verification
        N = len(candidates)
        M = len(zones)
        zone_weights_dict = _compute_zone_weights(zones)
        zone_ids = [z["zone_id"] for z in zones]
        zone_weights_arr = np.array([zone_weights_dict[zid] for zid in zone_ids], dtype=float)

        cand_coverage_dict = _compute_candidate_coverage(candidates, zones, coverage_radius_km)
        A = np.zeros((M, N), dtype=int)
        for c_idx, c in enumerate(candidates):
            c_cov = cand_coverage_dict.get(c["candidate_id"], set())
            for z_idx, zid in enumerate(zone_ids):
                if zid in c_cov:
                    A[z_idx, c_idx] = 1

        # 3. Solve via QAOA
        q_result = self.solver.solve(
            qubo_result=qubo_result,
            coverage_matrix=A,
            zone_weights=zone_weights_arr,
            config=config,
        )

        # 4. Map selected candidates back to domain objects
        candidate_lookup = {c["candidate_id"]: c for c in candidates}
        selected_sensors = [
            candidate_lookup[cid]
            for cid in q_result.selected_candidate_ids
            if cid in candidate_lookup
        ]

        # 5. Compute standard domain coverage metrics for OptimizationResult
        covered_zone_ids = set()
        for s in selected_sensors:
            covered_zone_ids |= cand_coverage_dict.get(s["candidate_id"], set())

        total_weight = sum(zone_weights_dict.values())
        covered_weight = sum(zone_weights_dict[zid] for zid in covered_zone_ids)
        coverage_pct = round(100.0 * covered_weight / total_weight, 2) if total_weight > 0 else 0.0

        crit_zones = [z for z in zones if z.get("risk_level") == "CRITICAL"]
        crit_covered = [z for z in crit_zones if z["zone_id"] in covered_zone_ids]
        crit_pct = round(100.0 * len(crit_covered) / len(crit_zones), 2) if crit_zones else 100.0

        uncovered_priority = [
            z["zone_id"] for z in zones
            if z.get("risk_level") in ("CRITICAL", "HIGH") and z["zone_id"] not in covered_zone_ids
        ]

        cov_per_sensor = round(covered_weight / max(1, len(selected_sensors)), 2)

        opt_result = OptimizationResult(
            engine_type="quantum_qaoa",
            selected_sensors=selected_sensors,
            coverage_percentage=coverage_pct,
            weighted_risk_coverage=round(covered_weight, 2),
            total_weighted_risk=round(total_weight, 2),
            critical_zone_coverage_percentage=crit_pct,
            covered_zone_ids=sorted(list(covered_zone_ids)),
            uncovered_priority_zone_ids=sorted(uncovered_priority),
            num_candidates_considered=N,
            num_sensors_requested=num_sensors,
            num_sensors_selected=len(selected_sensors),
            coverage_per_sensor=cov_per_sensor,
            minimal_sensors_for_max_coverage=len(selected_sensors),
        )

        return opt_result, q_result
