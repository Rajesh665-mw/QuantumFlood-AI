"""
Quantum QAOA Configuration
==========================
Defines configuration parameters for the Quantum Approximate Optimization Algorithm (QAOA).
"""
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class QaoaConfig:
    """
    Configuration parameters for QAOA execution.
    
    Attributes:
        p: Number of QAOA alternating operator steps (circuit depth). Recommended 1 or 2.
        shots: Number of measurement bitstrings sampled from the final quantum statevector.
        max_iter: Maximum iterations for classical outer-loop parameter optimizer (e.g. COBYLA).
        optimizer_method: Classical parameter optimizer: "COBYLA" or "Nelder-Mead".
        seed: Deterministic random seed for reproducibility.
        penalty: Optional manual penalty multiplier P. If None, analytically chosen.
        formulation_mode: "pairwise" (N qubits, exact for K<=2) or "exact" (with auxiliary qubits).
        initial_gamma: Optional initial gamma parameters of length p.
        initial_beta: Optional initial beta parameters of length p.
        tolerance: Convergence tolerance for classical optimizer.
    """
    p: int = 1
    shots: int = 1024
    max_iter: int = 100
    optimizer_method: str = "COBYLA"
    seed: Optional[int] = 42
    penalty: Optional[float] = None
    formulation_mode: str = "pairwise"
    initial_gamma: Optional[List[float]] = None
    initial_beta: Optional[List[float]] = None
    tolerance: float = 1e-4

    def __post_init__(self):
        if self.p < 1:
            raise ValueError(f"QAOA depth p must be >= 1, got {self.p}.")
        if self.shots < 1:
            raise ValueError(f"Number of shots must be >= 1, got {self.shots}.")
        if self.max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {self.max_iter}.")
        if self.formulation_mode not in ("pairwise", "exact"):
            raise ValueError(f"Invalid formulation_mode '{self.formulation_mode}'. Must be 'pairwise' or 'exact'.")
