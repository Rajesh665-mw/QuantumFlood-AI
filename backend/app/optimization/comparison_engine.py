"""
Classical vs Quantum Optimization Comparison Engine
===================================================
Executes identical sensor placement problem instances across:
  A. Classical Greedy Optimizer (provably (1 - 1/e)-approximate)
  B. Quantum QAOA Optimizer (p-depth parameterized variational quantum circuit)
  C. Exhaustive Combinatorial Solver (exact ground truth, when problem size N <= 12)

Provides an objective, mathematically rigorous comparison without promotional claims.
"""
import time
import math
import itertools
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import numpy as np

from app.optimization.classical_optimizer import (
    ClassicalOptimizationEngine,
    OptimizationResult,
    _compute_zone_weights,
    _compute_candidate_coverage,
)
from app.optimization.connectivity_analyzer import analyze_connectivity
from app.optimization.qubo_builder import compute_minimal_nodes_frontier
from app.quantum.quantum_optimizer import QuantumOptimizationEngine
from app.quantum.quantum_result import QuantumOptimizationResult


class OptimizationComparisonEngine:
    """
    Side-by-side solver comparator for sensor placement.
    """

    def __init__(self):
        self.classical_engine = ClassicalOptimizationEngine()
        self.quantum_engine = QuantumOptimizationEngine()

    def _solve_exhaustive_optimum(
        self,
        candidates: List[Dict[str, Any]],
        zones: List[Dict[str, Any]],
        coverage_radius_km: float,
        num_sensors: int,
    ) -> Dict[str, Any]:
        """
        Computes the global maximum coverage by exhaustively testing all binom(N, K) combinations.
        Only executed when N <= 12 to maintain interactive responsiveness.
        """
        N = len(candidates)
        K = min(num_sensors, N)
        zone_weights = _compute_zone_weights(zones)
        cand_coverage = _compute_candidate_coverage(candidates, zones, coverage_radius_km)
        total_weight = sum(zone_weights.values())

        best_coverage = -1.0
        best_subsets = []

        for subset in itertools.combinations(candidates, K):
            covered_zids = set()
            for c in subset:
                covered_zids |= cand_coverage.get(c["candidate_id"], set())
            cov_weight = sum(zone_weights[zid] for zid in covered_zids)
            if cov_weight > best_coverage + 1e-9:
                best_coverage = cov_weight
                best_subsets = [[c["candidate_id"] for c in subset]]
            elif abs(cov_weight - best_coverage) <= 1e-9:
                best_subsets.append([c["candidate_id"] for c in subset])

        cov_pct = round(100.0 * best_coverage / total_weight, 2) if total_weight > 0 else 0.0

        return {
            "optimal_weighted_coverage": round(best_coverage, 4),
            "optimal_coverage_percentage": cov_pct,
            "optimal_subsets_count": len(best_subsets),
            "optimal_sensor_subsets": best_subsets[:5],
            "total_subsets_evaluated": int(math.comb(N, K)),
        }

    def compare(
        self,
        candidates: List[Dict[str, Any]],
        zones: List[Dict[str, Any]],
        coverage_radius_km: float,
        num_sensors: int,
        p: int = 1,
        shots: int = 1024,
        seed: Optional[int] = 42,
        run_exhaustive_if_feasible: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes both solvers on identical inputs and generates a comparative assessment.
        """
        N = len(candidates)
        K = min(num_sensors, N)

        # 1. Classical Execution
        t0 = time.perf_counter()
        classical_opt = self.classical_engine.optimize(
            candidates, zones, coverage_radius_km, num_sensors
        )
        classical_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        # 2. Quantum QAOA Execution
        t1 = time.perf_counter()
        quantum_opt, quantum_raw = self.quantum_engine.optimize(
            candidates, zones, coverage_radius_km, num_sensors, p=p, shots=shots, seed=seed
        )
        quantum_time_ms = round((time.perf_counter() - t1) * 1000.0, 2)

        # 3. Exhaustive Global Optimum (if N <= 12)
        exhaustive_result = None
        if run_exhaustive_if_feasible and N <= 12:
            exhaustive_result = self._solve_exhaustive_optimum(
                candidates, zones, coverage_radius_km, num_sensors
            )

        # 4. Comparative Metrics
        c_sensors = set(s["candidate_id"] for s in classical_opt.selected_sensors)
        q_sensors = set(s["candidate_id"] for s in quantum_opt.selected_sensors)

        intersection = c_sensors & q_sensors
        union = c_sensors | q_sensors
        jaccard = round(len(intersection) / len(union), 4) if union else 1.0

        c_cov = classical_opt.weighted_risk_coverage
        q_cov = quantum_opt.weighted_risk_coverage

        ratio_to_classical = round(q_cov / c_cov, 4) if c_cov > 0 else 1.0

        ratio_to_optimum = None
        c_ratio_to_optimum = None
        if exhaustive_result is not None:
            opt_cov = exhaustive_result["optimal_weighted_coverage"]
            if opt_cov > 0:
                ratio_to_optimum = round(q_cov / opt_cov, 4)
                c_ratio_to_optimum = round(c_cov / opt_cov, 4)

        # Academic Assessment Narrative
        if exhaustive_result is not None:
            opt_cov = exhaustive_result["optimal_weighted_coverage"]
            if abs(q_cov - opt_cov) < 1e-4:
                assessment = (
                    f"Quantum QAOA (depth p={p}) discovered a mathematically global optimum "
                    f"matching the exhaustive combinatorial search (Coverage: {q_cov:.1f})."
                )
            elif q_cov >= c_cov:
                assessment = (
                    f"Quantum QAOA matched or exceeded classical greedy coverage "
                    f"(Achieved {ratio_to_optimum * 100:.1f}% of global optimum)."
                )
            else:
                assessment = (
                    f"Quantum QAOA achieved {ratio_to_optimum * 100:.1f}% of global optimum "
                    f"(Classical greedy achieved {c_ratio_to_optimum * 100:.1f}%). "
                    f"Increasing depth p or shots may improve variational convergence."
                )
        else:
            if abs(q_cov - c_cov) < 1e-4:
                assessment = "Quantum QAOA matched the classical greedy solution's coverage exactly."
            elif q_cov > c_cov:
                assessment = f"Quantum QAOA found a solution with {q_cov - c_cov:.1f} higher weighted coverage than classical greedy."
            else:
                assessment = f"Quantum QAOA achieved {ratio_to_classical * 100:.1f}% of the classical greedy coverage."

        # 5. Communication Node Analysis (Stage 2)
        comm_range = coverage_radius_km * 1.5
        max_comm = max(1, K)
        c_conn = analyze_connectivity(classical_opt.selected_sensors, comm_range_km=comm_range, max_comm_nodes=max_comm)
        q_conn = analyze_connectivity(quantum_opt.selected_sensors, comm_range_km=comm_range, max_comm_nodes=max_comm)

        # 6. Minimal Nodes & Pareto Frontier Analysis (UC-067 Target A)
        minimal_frontier = compute_minimal_nodes_frontier(
            candidates=candidates,
            zones=zones,
            coverage_radius_km=coverage_radius_km,
            max_k=min(N, max(K + 2, 6)),
        )

        return {
            "problem_size": {
                "num_candidates": N,
                "num_zones": len(zones),
                "budget_k": K,
                "coverage_radius_km": coverage_radius_km,
            },
            "classical_result": {
                "selected_sensor_ids": sorted(list(c_sensors)),
                "num_sensors_selected": classical_opt.num_sensors_selected,
                "weighted_coverage": classical_opt.weighted_risk_coverage,
                "coverage_percentage": classical_opt.coverage_percentage,
                "critical_zone_coverage_pct": classical_opt.critical_zone_coverage_percentage,
                "coverage_per_sensor": classical_opt.coverage_per_sensor,
                "minimal_sensors_for_max_coverage": classical_opt.minimal_sensors_for_max_coverage,
                "execution_time_ms": classical_time_ms,
            },
            "quantum_result": {
                "selected_sensor_ids": sorted(list(q_sensors)),
                "num_sensors_selected": quantum_opt.num_sensors_selected,
                "weighted_coverage": quantum_opt.weighted_risk_coverage,
                "coverage_percentage": quantum_opt.coverage_percentage,
                "critical_zone_coverage_pct": quantum_opt.critical_zone_coverage_percentage,
                "coverage_per_sensor": quantum_opt.coverage_per_sensor,
                "minimal_sensors_for_max_coverage": quantum_opt.minimal_sensors_for_max_coverage,
                "is_feasible": quantum_raw.is_feasible,
                "qaoa_depth_p": quantum_raw.qaoa_depth_p,
                "shots": quantum_raw.shots,
                "solution_probability": quantum_raw.solution_probability,
                "qubo_energy": quantum_raw.qubo_energy,
                "execution_time_ms": quantum_time_ms,
                "optimal_gamma": quantum_raw.optimal_gamma,
                "optimal_beta": quantum_raw.optimal_beta,
            },
            "exhaustive_ground_truth": exhaustive_result,
            "comparison_metrics": {
                "shared_sensors_count": len(intersection),
                "jaccard_similarity": jaccard,
                "coverage_delta": round(q_cov - c_cov, 4),
                "quantum_to_classical_ratio": ratio_to_classical,
                "quantum_approximation_ratio": ratio_to_optimum,
                "classical_approximation_ratio": c_ratio_to_optimum,
                "quantum_matched_classical": bool(abs(q_cov - c_cov) < 1e-4),
                "quantum_matched_global_optimum": bool(
                    exhaustive_result is not None and abs(q_cov - exhaustive_result["optimal_weighted_coverage"]) < 1e-4
                ),
            },
            "communication_nodes_analysis": {
                "comm_range_km": comm_range,
                "max_comm_nodes_budget": max_comm,
                "classical": {
                    "sensor_nodes_count": len(classical_opt.selected_sensors),
                    "comm_nodes_used": c_conn.comm_nodes_used,
                    "max_comm_nodes_allowed": c_conn.max_comm_nodes,
                    "connectivity_percentage": c_conn.connectivity_percentage,
                    "disconnected_nodes_count": len(c_conn.disconnected_sensor_ids),
                    "disconnected_sensor_ids": list(c_conn.disconnected_sensor_ids),
                    "relay_nodes_count": len(c_conn.comm_nodes),
                },
                "quantum": {
                    "sensor_nodes_count": len(quantum_opt.selected_sensors),
                    "comm_nodes_used": q_conn.comm_nodes_used,
                    "max_comm_nodes_allowed": q_conn.max_comm_nodes,
                    "connectivity_percentage": q_conn.connectivity_percentage,
                    "disconnected_nodes_count": len(q_conn.disconnected_sensor_ids),
                    "disconnected_sensor_ids": list(q_conn.disconnected_sensor_ids),
                    "relay_nodes_count": len(q_conn.comm_nodes),
                },
            },
            "minimal_nodes_analysis": minimal_frontier,
            "academic_assessment": assessment,
        }
