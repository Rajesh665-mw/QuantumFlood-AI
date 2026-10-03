"""
QML Forecast Result Data Structure
==================================
Encapsulates the training, inference, and evaluation metrics of the
Variational Quantum Regressor (VQR) for hydrological forecasting.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class QmlForecastResult:
    """
    Standardized result structure for QML continuous water-level regression.
    """
    engine_type: str = "quantum_vqr"
    model_name: str = "quantum_variational_regressor"
    horizon_days: int = 1
    train_size: int = 0
    test_size: int = 0
    qubits: int = 4
    circuit_depth_layers: int = 2
    trainable_parameters_count: int = 16
    optimal_parameters: List[float] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    predictions: List[Dict[str, Any]] = field(default_factory=list)
    feature_names: List[str] = field(default_factory=list)
    training_time_ms: float = 0.0
    inference_time_ms: float = 0.0
    simulator_name: str = "Pure NumPy Statevector"
    training_loss_history: List[float] = field(default_factory=list)
    scaling_params: Dict[str, Any] = field(default_factory=dict)
    affine_w: float = 1.0
    affine_b: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def test_mae(self) -> float:
        return float(self.metrics.get("mae", 0.0))

    @property
    def test_rmse(self) -> float:
        return float(self.metrics.get("rmse", 0.0))

    @property
    def test_r2(self) -> float:
        return float(self.metrics.get("r2", 0.0))

    @property
    def n_qubits(self) -> int:
        return self.qubits

    @property
    def n_parameters(self) -> int:
        return self.trainable_parameters_count

    @property
    def circuit_depth(self) -> int:
        return 11

    @property
    def training_time_s(self) -> float:
        return round(self.training_time_ms / 1000.0, 3)

    @property
    def inference_time_s(self) -> float:
        return round(self.inference_time_ms / 1000.0, 3)

    @property
    def simulator(self) -> str:
        return self.simulator_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine_type": self.engine_type,
            "model_name": self.model_name,
            "horizon_days": self.horizon_days,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "qubits": self.qubits,
            "n_qubits": self.qubits,
            "circuit_depth": 11,
            "circuit_depth_layers": self.circuit_depth_layers,
            "trainable_parameters_count": self.trainable_parameters_count,
            "n_parameters": self.trainable_parameters_count,
            "optimal_parameters": [round(float(p), 6) for p in self.optimal_parameters],
            "metrics": {k: round(float(v), 4) for k, v in self.metrics.items()},
            "test_mae": round(self.test_mae, 4),
            "test_rmse": round(self.test_rmse, 4),
            "test_r2": round(self.test_r2, 4),
            "predictions": self.predictions,
            "feature_names": self.feature_names,
            "training_time_ms": round(float(self.training_time_ms), 2),
            "inference_time_ms": round(float(self.inference_time_ms), 2),
            "training_time_s": self.training_time_s,
            "inference_time_s": self.inference_time_s,
            "simulator_name": self.simulator_name,
            "affine_w": round(float(self.affine_w), 6),
            "affine_b": round(float(self.affine_b), 6),
            "scaling_params": self.scaling_params,
            "metadata": self.metadata,
        }
