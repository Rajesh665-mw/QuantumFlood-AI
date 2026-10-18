"""
Shelter Portfolio Optimizer
===========================
Hybrid Quantum-Classical Portfolio Selection for Proposed Candidate Shelter Sites.

Mathematical Formulation:
  Select K proposed shelter sites from N candidates to maximize collective MCDA
  suitability while penalizing spatial clustering (ensuring wide geographical spread
  for evacuee access):

    H(y) = -sum_{i=0}^{N-1} S_i y_i + lambda * sum_{i < j} Overlap(i, j) y_i y_j + P * (sum_i y_i - K)^2

  where:
    y_i in {0, 1} indicates selection of proposed shelter candidate i.
    S_i is the normalized MCDA suitability score (0 - 100).
    Overlap(i, j) = max(0, 1 - dist(i, j) / d_min) penalizes redundant co-location.
    P > max(S_i) is the analytically safe budget penalty.
"""
import time
import math
import itertools
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from app.utils.geo_math import haversine_km
from app.quantum.qaoa_solver import QaoaSolver
from app.quantum.quantum_config import QaoaConfig
from app.optimization.qubo_builder import (
    recommend_penalty,
    evaluate_qubo,
    decode_solution,
    repair_bitstring_to_budget,
    QuboResult,
)


def build_shelter_portfolio_qubo(
    candidate_shelters: List[Dict[str, Any]],
    budget: int,
    min_separation_km: float = 2.0,
    cluster_penalty_weight: float = 25.0,
    penalty: Optional[float] = None,
) -> QuboResult:
    """
    Constructs an upper-triangular QUBO matrix for shelter portfolio selection.
    """
    N = len(candidate_shelters)
    if N == 0:
        raise ValueError("Candidate shelter list cannot be empty.")
    if budget < 1 or budget > N:
        raise ValueError(f"Budget K must satisfy 1 <= K <= {N}, got {budget}.")

    K = int(budget)
    scores = np.array([float(s.get("suitability_score", s.get("recommendation_score", 50.0))) for s in candidate_shelters], dtype=float)

    P = penalty if penalty is not None else recommend_penalty(scores, multiplier=1.5)

    Q = np.zeros((N, N), dtype=float)

    # Diagonal terms: -S_i + P * (1 - 2*K)
    for i in range(N):
        Q[i, i] = -scores[i] + P * (1.0 - 2.0 * K)

    # Off-diagonal terms: Overlap penalty + 2*P
    for i in range(N):
        c_i = candidate_shelters[i]
        lat_i, lon_i = c_i["lat"], c_i["lon"]
        for j in range(i + 1, N):
            c_j = candidate_shelters[j]
            lat_j, lon_j = c_j["lat"], c_j["lon"]
            d_km = haversine_km(lat_i, lon_i, lat_j, lon_j)
            overlap = max(0.0, 1.0 - (d_km / min_separation_km))
            clustering_cost = cluster_penalty_weight * overlap
            Q[i, j] = clustering_cost + 2.0 * P

    offset = float(P * (K ** 2))
    cand_ids = [s.get("id", f"SL-{i:02d}") for i, s in enumerate(candidate_shelters)]

    return QuboResult(
        Q=Q,
        offset=offset,
        alpha=scores,
        beta=np.zeros((N, N)),
        penalty=P,
        num_variables=N,
        budget=K,
        candidate_ids=cand_ids,
        metadata={
            "formulation": "shelter_portfolio_mcda_dispersion",
            "min_separation_km": min_separation_km,
            "cluster_penalty_weight": cluster_penalty_weight,
            "candidate_count": N,
            "budget": K,
        },
    )


class ShelterPortfolioOptimizer:
    """
    Executes hybrid quantum-classical optimization for selecting proposed shelter site portfolios.
    """

    def __init__(self):
        self.qaoa_solver = QaoaSolver()

    def solve_classical_greedy(
        self,
        candidate_shelters: List[Dict[str, Any]],
        budget: int,
        min_separation_km: float = 2.0,
    ) -> Dict[str, Any]:
        """Classical greedy heuristic maximizing suitability with dispersion penalties."""
        t0 = time.perf_counter()
        N = len(candidate_shelters)
        K = min(budget, N)
        selected_indices: List[int] = []
        remaining = set(range(N))

        while len(selected_indices) < K and remaining:
            best_idx = None
            best_val = -float("inf")
            for idx in remaining:
                cand = candidate_shelters[idx]
                score = float(cand.get("suitability_score", cand.get("recommendation_score", 50.0)))
                # Penalize proximity to already selected
                proximity_penalty = 0.0
                for s_idx in selected_indices:
                    prev = candidate_shelters[s_idx]
                    d = haversine_km(cand["lat"], cand["lon"], prev["lat"], prev["lon"])
                    if d < min_separation_km:
                        proximity_penalty += 25.0 * (1.0 - d / min_separation_km)
                net_val = score - proximity_penalty
                if net_val > best_val:
                    best_val = net_val
                    best_idx = idx

            if best_idx is not None:
                selected_indices.append(best_idx)
                remaining.remove(best_idx)

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        selected_shelters = [candidate_shelters[i] for i in selected_indices]
        tot_score = sum(float(s.get("suitability_score", s.get("recommendation_score", 50.0))) for s in selected_shelters)

        return {
            "solver": "classical_greedy",
            "selected_shelters": selected_shelters,
            "selected_ids": [s["id"] for s in selected_shelters],
            "total_suitability_score": round(tot_score, 2),
            "execution_time_ms": elapsed_ms,
            "is_feasible": len(selected_shelters) == K,
        }

    def solve_exhaustive_optimum(
        self,
        candidate_shelters: List[Dict[str, Any]],
        qubo_result: QuboResult,
        budget: int,
    ) -> Dict[str, Any]:
        """Exhaustive ground truth across all binom(N, K) combinations (practical for N <= 14)."""
        N = len(candidate_shelters)
        K = min(budget, N)
        best_energy = float("inf")
        best_subset = []

        for subset in itertools.combinations(range(N), K):
            x = np.zeros(N, dtype=int)
            for idx in subset:
                x[idx] = 1
            E = evaluate_qubo(x, qubo_result.Q, qubo_result.offset)
            if E < best_energy:
                best_energy = E
                best_subset = list(subset)

        selected_shelters = [candidate_shelters[i] for i in best_subset]
        tot_score = sum(float(s.get("suitability_score", s.get("recommendation_score", 50.0))) for s in selected_shelters)

        return {
            "solver": "exhaustive_combinatorial",
            "selected_shelters": selected_shelters,
            "selected_ids": [s["id"] for s in selected_shelters],
            "total_suitability_score": round(tot_score, 2),
            "qubo_energy": round(best_energy, 4),
            "total_subsets_evaluated": int(math.comb(N, K)),
        }

    def optimize_portfolio(
        self,
        candidate_shelters: List[Dict[str, Any]],
        budget: int = 3,
        min_separation_km: float = 2.0,
        p: int = 1,
        shots: int = 512,
        seed: Optional[int] = 42,
    ) -> Dict[str, Any]:
        """
        Executes hybrid quantum QAOA portfolio selection and returns comparative audit.
        """
        t0 = time.perf_counter()
        N = len(candidate_shelters)
        K = min(budget, N)

        # 1. Build QUBO
        qubo = build_shelter_portfolio_qubo(
            candidate_shelters=candidate_shelters,
            budget=K,
            min_separation_km=min_separation_km,
        )

        # 2. Classical Baseline
        classical_sol = self.solve_classical_greedy(
            candidate_shelters=candidate_shelters,
            budget=K,
            min_separation_km=min_separation_km,
        )

        # 3. Exhaustive Global Optimum
        exhaustive_sol = None
        if N <= 14:
            exhaustive_sol = self.solve_exhaustive_optimum(
                candidate_shelters=candidate_shelters,
                qubo_result=qubo,
                budget=K,
            )

        # 4. Quantum QAOA Execution
        # In this formulation, coverage matrix is identity for candidate selection
        cov_matrix = np.eye(N, dtype=int)
        scores = qubo.alpha
        config = QaoaConfig(p=p, shots=shots, seed=seed)

        q_res = self.qaoa_solver.solve(
            qubo_result=qubo,
            coverage_matrix=cov_matrix,
            zone_weights=scores,
            config=config,
        )
        quantum_time_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        selected_indices = q_res.selected_indices
        selected_shelters = [candidate_shelters[i] for i in selected_indices if i < N]
        q_score = sum(float(s.get("suitability_score", s.get("recommendation_score", 50.0))) for s in selected_shelters)

        # Calculate dispersion: minimum distance between any selected pair
        min_dist_pair = None
        if len(selected_shelters) >= 2:
            min_d = float("inf")
            for i in range(len(selected_shelters)):
                for j in range(i + 1, len(selected_shelters)):
                    d = haversine_km(
                        selected_shelters[i]["lat"], selected_shelters[i]["lon"],
                        selected_shelters[j]["lat"], selected_shelters[j]["lon"]
                    )
                    if d < min_d:
                        min_d = d
            min_dist_pair = round(min_d, 2)

        return {
            "engine_type": "quantum_qaoa_portfolio",
            "target_budget": K,
            "candidate_count": N,
            "min_separation_km": min_separation_km,
            "selected_shelters": selected_shelters,
            "selected_ids": [s["id"] for s in selected_shelters],
            "total_suitability_score": round(q_score, 2),
            "minimum_pairwise_distance_km": min_dist_pair,
            "is_feasible": q_res.is_feasible,
            "qubo_energy": q_res.qubo_energy,
            "execution_time_ms": quantum_time_ms,
            "quantum_metadata": {
                "qubits": q_res.total_qubits,
                "qaoa_depth_p": q_res.qaoa_depth_p,
                "shots": q_res.shots,
                "backend": q_res.backend_name,
                "circuit_depth": q_res.metadata.get("circuit_depth"),
                "cnot_count": q_res.metadata.get("cnot_count"),
                "was_repaired": q_res.metadata.get("was_repaired", False),
            },
            "classical_baseline": classical_sol,
            "exhaustive_optimum": exhaustive_sol,
            "scientific_note": (
                "Portfolio optimization evaluated on proposed shelter candidates. "
                "Operational municipal shelters remain active and unaffected. "
                "QAOA balances aggregate suitability against spatial clustering."
            ),
        }
