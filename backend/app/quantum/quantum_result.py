"""
Quantum Optimization Result Data Structure
==========================================
Encapsulates the output of the QAOA quantum optimization solver.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class QuantumOptimizationResult:
    """
    Standardized result structure for quantum sensor placement optimization.
    """
    selected_candidate_ids: List[str]
    selected_indices: List[int]
    binary_solution: List[int]
    objective_value: float
    weighted_coverage: float
    sensor_budget: int
    sensors_selected_count: int
    is_feasible: bool
    qubo_energy: float
    qaoa_depth_p: int
    optimal_gamma: List[float]
    optimal_beta: List[float]
    shots: int
    backend_name: str
    execution_time_ms: float
    solution_probability: float
    total_qubits: int
    state_probabilities: Dict[str, float] = field(default_factory=dict)
    candidate_coverage_details: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_candidate_ids": self.selected_candidate_ids,
            "selected_indices": self.selected_indices,
            "binary_solution": self.binary_solution,
            "objective_value": round(float(self.objective_value), 4),
            "weighted_coverage": round(float(self.weighted_coverage), 4),
            "sensor_budget": self.sensor_budget,
            "sensors_selected_count": self.sensors_selected_count,
            "is_feasible": bool(self.is_feasible),
            "qubo_energy": round(float(self.qubo_energy), 6),
            "qaoa_depth_p": self.qaoa_depth_p,
            "optimal_gamma": [round(float(g), 6) for g in self.optimal_gamma],
            "optimal_beta": [round(float(b), 6) for b in self.optimal_beta],
            "shots": self.shots,
            "backend_name": self.backend_name,
            "execution_time_ms": round(float(self.execution_time_ms), 2),
            "solution_probability": round(float(self.solution_probability), 6),
            "total_qubits": self.total_qubits,
            "state_probabilities": {k: round(float(v), 6) for k, v in self.state_probabilities.items()},
            "candidate_coverage_details": self.candidate_coverage_details,
            "metadata": self.metadata,
        }
