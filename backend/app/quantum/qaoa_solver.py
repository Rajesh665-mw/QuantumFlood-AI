"""
QAOA Solver for Sensor Placement Optimization
==============================================
Implements the Quantum Approximate Optimization Algorithm (QAOA) using a high-performance,
deterministic statevector quantum simulator engine in pure NumPy.

Formulation:
    1. Problem Hamiltonian H_C:
       Derived from the QUBO formulation: H_C |x> = (x^T Q x + offset) |x>.
       Because H_C is diagonal in the computational basis, the unitary operator
       U(H_C, gamma) = exp(-i * gamma * H_C) acts as an element-wise phase shift:
           exp(-i * gamma * H_C) |x> = exp(-i * gamma * E(x)) |x>.
    2. Mixer Hamiltonian H_M:
       Standard transverse-field mixer H_M = sum_{j=0}^{N-1} X_j.
       U(H_M, beta) = exp(-i * beta * H_M) = (X-rotation gate R_x(2*beta)) applied to each qubit.
    3. Quantum Statevector evolution:
       |psi(gamma, beta)> = prod_{l=1}^p [ U(H_M, beta_l) U(H_C, gamma_l) ] |+>^N.
    4. Classical Optimization Loop:
       Scipy COBYLA optimizer iteratively searches for parameter angles (gamma, beta)
       that minimize the expectation value <psi | H_C | psi>.
    5. Measurement & Sampling:
       Bitstrings are sampled according to |psi_x|^2. The best feasible candidate
       configuration is extracted, validated against ground-truth coverage, and returned.
"""
import time
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from scipy.optimize import minimize

from app.quantum.quantum_config import QaoaConfig
from app.quantum.quantum_result import QuantumOptimizationResult
from app.optimization.qubo_builder import (
    build_sensor_qubo,
    evaluate_qubo,
    decode_solution,
    compute_actual_coverage,
    QuboResult,
)


class QaoaSolver:
    """
    Simulates QAOA circuits locally using an exact statevector representation.
    """

    def __init__(self, config: Optional[QaoaConfig] = None):
        self.config = config or QaoaConfig()

    def _precompute_basis_and_energies(self, Q: np.ndarray, offset: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Precomputes the 2^N computational basis states and their diagonal QUBO energies.
        """
        N = Q.shape[0]
        if N > 20:
            raise ValueError(f"Statevector simulation requires N <= 20 qubits for practical memory; got N={N}.")
        dim = 1 << N
        # Precompute basis array of shape (dim, N)
        basis = np.array([[ (i >> (N - 1 - j)) & 1 for j in range(N) ] for i in range(dim)], dtype=float)
        
        # Diagonal QUBO energies for each basis state
        # E(x) = sum_j Q_jj x_j + sum_{j<k} Q_jk x_j x_k + offset
        energies = np.zeros(dim, dtype=float)
        for i in range(dim):
            x = basis[i]
            energies[i] = float(x @ Q @ x + offset)
        
        return basis, energies

    def _simulate_circuit(
        self,
        angles: np.ndarray,
        p: int,
        energies: np.ndarray,
        dim: int,
        N: int,
    ) -> Tuple[float, np.ndarray]:
        """
        Evolves the statevector |+>^N through p alternating layers of cost and mixer unitaries.
        Returns the scalar expectation value <psi | H_C | psi> and the state probability distribution.
        """
        gammas = angles[:p]
        betas = angles[p:]

        # Initialize uniform superposition |+>^N = sum |x> / sqrt(2^N)
        psi = np.full(dim, 1.0 / np.sqrt(dim), dtype=complex)

        # Alternating layers
        for l in range(p):
            gamma = gammas[l]
            beta = betas[l]

            # 1. Cost unitary: exp(-i * gamma * H_C) (diagonal phase shift)
            psi = psi * np.exp(-1j * gamma * energies)

            # 2. Mixer unitary: exp(-i * beta * sum X_j) = tensor prod of exp(-i * beta * X)
            # exp(-i * beta * X) = [[cos(beta), -i*sin(beta)], [-i*sin(beta), cos(beta)]]
            c = np.cos(beta)
            s = -1j * np.sin(beta)
            rot = np.array([[c, s], [s, c]], dtype=complex)

            # Reshape into N-dimensional tensor of shape (2, 2, ..., 2)
            psi_tensor = psi.reshape([2] * N)
            for q in range(N):
                # Contract 2x2 rotation matrix with axis q
                psi_tensor = np.tensordot(rot, psi_tensor, axes=([1], [q]))
                # Move rotated axis back to position q
                psi_tensor = np.moveaxis(psi_tensor, 0, q)
            psi = psi_tensor.flatten()

        probs = np.abs(psi) ** 2
        expectation = float(np.dot(probs, energies))
        return expectation, probs

    def solve(
        self,
        qubo_result: QuboResult,
        coverage_matrix: np.ndarray,
        zone_weights: np.ndarray,
        config: Optional[QaoaConfig] = None,
    ) -> QuantumOptimizationResult:
        """
        Executes QAOA on the provided QUBO problem.
        """
        cfg = config or self.config
        start_time = time.perf_counter()

        Q = qubo_result.Q
        offset = qubo_result.offset
        total_qubits = qubo_result.num_variables
        p = cfg.p
        budget = qubo_result.budget

        # 1. Precompute basis and energies
        basis, energies = self._precompute_basis_and_energies(Q, offset)
        dim = 1 << total_qubits

        # 2. Setup initial parameters
        if cfg.seed is not None:
            np.random.seed(cfg.seed)

        if cfg.initial_gamma is not None and len(cfg.initial_gamma) == p:
            init_gamma = list(cfg.initial_gamma)
        else:
            # Linear schedule heuristic: gamma_l = (l/p) * (pi/2)
            init_gamma = [float((l + 1) / p * 0.5 * np.pi) for l in range(p)]

        if cfg.initial_beta is not None and len(cfg.initial_beta) == p:
            init_beta = list(cfg.initial_beta)
        else:
            # Linear schedule heuristic: beta_l = (1 - l/p) * (pi/4)
            init_beta = [float((1.0 - l / p) * 0.25 * np.pi) for l in range(p)]

        x0 = np.array(init_gamma + init_beta, dtype=float)

        # 3. Outer-loop classical optimization (COBYLA)
        def objective_fn(angles: np.ndarray) -> float:
            exp_val, _ = self._simulate_circuit(angles, p, energies, dim, total_qubits)
            return exp_val

        opt_res = minimize(
            objective_fn,
            x0=x0,
            method=cfg.optimizer_method,
            options={"maxiter": cfg.max_iter, "tol": cfg.tolerance},
        )

        optimal_angles = opt_res.x
        optimal_gamma = [float(g) for g in optimal_angles[:p]]
        optimal_beta = [float(b) for b in optimal_angles[p:]]

        # 4. Final statevector and probability distribution
        final_exp, probs = self._simulate_circuit(optimal_angles, p, energies, dim, total_qubits)

        # 5. Measurement / Shot Sampling
        rng = np.random.RandomState(cfg.seed) if cfg.seed is not None else np.random.RandomState()
        sampled_indices = rng.choice(dim, size=cfg.shots, p=probs)
        unique_states, counts = np.unique(sampled_indices, return_counts=True)

        # Map candidate IDs (extract original N candidates)
        num_candidates = qubo_result.metadata.get("num_candidates", total_qubits)
        candidate_ids = qubo_result.candidate_ids[:num_candidates]

        # Evaluate sampled states
        evaluated_samples = []
        for state_idx, count in zip(unique_states, counts):
            bitstring = basis[state_idx].astype(int)
            E = energies[state_idx]
            decoded = decode_solution(
                bitstring,
                candidate_ids=candidate_ids,
                expected_budget=budget,
                num_candidates=num_candidates,
            )
            cand_vector = decoded["binary_vector"]
            cov = compute_actual_coverage(cand_vector, coverage_matrix, zone_weights)
            
            evaluated_samples.append({
                "state_idx": int(state_idx),
                "bitstring": bitstring.tolist(),
                "candidate_vector": cand_vector,
                "selected_indices": decoded["selected_indices"],
                "selected_ids": decoded["selected_candidate_ids"],
                "is_feasible": decoded["is_feasible"],
                "energy": float(E),
                "coverage": float(cov),
                "count": int(count),
                "probability": float(probs[state_idx]),
            })

        # Select best feasible state (lowest energy / highest coverage)
        feasible_samples = [s for s in evaluated_samples if s["is_feasible"]]
        if feasible_samples:
            # Sort by energy ascending (min energy)
            feasible_samples.sort(key=lambda s: s["energy"])
            best_sample = feasible_samples[0]
        else:
            # Fallback to overall lowest energy state if no feasible state was sampled
            evaluated_samples.sort(key=lambda s: s["energy"])
            best_sample = evaluated_samples[0]

        execution_time_ms = (time.perf_counter() - start_time) * 1000.0

        # Extract top state probabilities for introspection
        top_prob_indices = np.argsort(probs)[::-1][:10]
        state_probs_dict = {
            "".join(str(int(b)) for b in basis[idx]): float(probs[idx])
            for idx in top_prob_indices
        }

        # Build candidate coverage details
        cand_details = []
        cov_mat = np.asarray(coverage_matrix, dtype=int)
        weights = np.asarray(zone_weights, dtype=float)
        for c_idx in best_sample["selected_indices"]:
            c_id = candidate_ids[c_idx] if c_idx < len(candidate_ids) else f"C-{c_idx}"
            covered_zones = [int(z) for z in range(cov_mat.shape[0]) if cov_mat[z, c_idx] == 1]
            c_weight = float(np.sum(weights[covered_zones]))
            cand_details.append({
                "candidate_id": c_id,
                "candidate_index": int(c_idx),
                "covered_zones_count": len(covered_zones),
                "individual_weight_sum": round(c_weight, 4),
            })

        return QuantumOptimizationResult(
            selected_candidate_ids=best_sample["selected_ids"],
            selected_indices=best_sample["selected_indices"],
            binary_solution=best_sample["candidate_vector"],
            objective_value=round(best_sample["coverage"], 4),
            weighted_coverage=round(best_sample["coverage"], 4),
            sensor_budget=budget,
            sensors_selected_count=len(best_sample["selected_indices"]),
            is_feasible=best_sample["is_feasible"],
            qubo_energy=round(best_sample["energy"], 6),
            qaoa_depth_p=p,
            optimal_gamma=optimal_gamma,
            optimal_beta=optimal_beta,
            shots=cfg.shots,
            backend_name="qaoa_numpy_statevector_simulator",
            execution_time_ms=round(execution_time_ms, 2),
            solution_probability=round(best_sample["probability"], 6),
            total_qubits=total_qubits,
            state_probabilities=state_probs_dict,
            candidate_coverage_details=cand_details,
            metadata={
                "optimizer_iterations": int(opt_res.nfev),
                "optimizer_message": str(opt_res.message),
                "optimizer_converged": bool(opt_res.success),
                "final_expectation_value": round(float(final_exp), 6),
                "sampled_states_count": len(evaluated_samples),
                "feasible_samples_count": len(feasible_samples),
                "formulation_mode": cfg.formulation_mode,
                "auxiliary_qubits": total_qubits - num_candidates,
            },
        )

    def optimize(
        self,
        coverage_matrix: np.ndarray,
        zone_weights: np.ndarray,
        budget: int,
        candidate_ids: Optional[List[str]] = None,
        config: Optional[QaoaConfig] = None,
    ) -> QuantumOptimizationResult:
        """
        Convenience wrapper that builds QUBO and executes QAOA end-to-end.
        """
        cfg = config or self.config
        qubo_result = build_sensor_qubo(
            coverage_matrix=coverage_matrix,
            zone_weights=zone_weights,
            budget=budget,
            penalty=cfg.penalty,
            candidate_ids=candidate_ids,
            mode=cfg.formulation_mode,
        )
        return self.solve(qubo_result, coverage_matrix, zone_weights, config=cfg)
