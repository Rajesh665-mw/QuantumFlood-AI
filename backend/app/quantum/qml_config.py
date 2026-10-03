"""
QML Forecasting Configuration
=============================
Defines configuration parameters for the 4-qubit Variational Quantum Regressor (VQR)
with data re-uploading for hydrological water-level forecasting.
"""
from dataclasses import dataclass, field
from typing import Optional, List


APPROVED_QML_FEATURES: List[str] = [
    "water_level_m",
    "inflow_ktcmd",
    "rainfall_roll3",
    "rainfall_mm",
]


@dataclass
class QmlConfig:
    """
    Configuration parameters for 4-qubit Variational Quantum Regressor.

    Attributes:
        n_qubits: Number of qubits (fixed to 4 per approved design).
        layers: Number of variational layers with data re-uploading (L=2).
        trainable_params_count: Expected parameter count: 4 qubits * 2 angles * 2 layers = 16.
        max_iter: Maximum iterations for classical outer-loop optimizer (COBYLA).
        seed: Deterministic random seed for reproducibility.
        optimizer_method: Classical parameter optimizer ("COBYLA" or "Nelder-Mead").
        train_subsample: Optional maximum training samples for fast interactive execution (e.g. 200).
        tolerance: Convergence tolerance for classical optimizer.
        features: Exact list and deterministic ordering of input features mapped to qubits 0..3.
    """
    n_qubits: int = 4
    layers: int = 2
    n_layers: Optional[int] = None
    trainable_params_count: int = 16
    max_iter: int = 80
    seed: int = 42
    optimizer_method: str = "COBYLA"
    train_subsample: Optional[int] = 200
    tolerance: float = 1e-4
    features: List[str] = field(default_factory=lambda: list(APPROVED_QML_FEATURES))

    def __post_init__(self):
        if self.n_layers is not None:
            self.layers = self.n_layers

        if self.n_qubits != 4:
            raise ValueError(f"QML Forecaster requires exactly 4 qubits; got {self.n_qubits}.")
        if self.layers != 2:
            raise ValueError(f"Approved VQR architecture requires exactly 2 layers; got {self.layers}.")
        expected_params = self.n_qubits * 2 * self.layers
        if self.trainable_params_count != expected_params:
            raise ValueError(
                f"Trainable parameter count mismatch: expected {expected_params} "
                f"(4 qubits * 2 angles * 2 layers), got {self.trainable_params_count}."
            )
        if len(self.features) != 4:
            raise ValueError(f"Approved QML design requires exactly 4 features; got {len(self.features)}.")
        if self.max_iter < 1:
            raise ValueError(f"max_iter must be >= 1, got {self.max_iter}.")

    @property
    def n_parameters(self) -> int:
        return self.trainable_params_count

    @property
    def circuit_depth(self) -> int:
        # Per layer: Ry (1) + Rz (1) + Rx (1) + 4 circular CNOTs (depth 4) = 7
        # 2 layers = 14 or 11 with parallel execution
        return 11
