"""
Pure NumPy Variational Quantum Regressor (VQR) for Hydrological Forecasting
===========================================================================
Implements a 4-qubit parameterized quantum circuit (PQC) with data re-uploading
for continuous water-level regression:

    Input Features (4):
        q0: water_level_m(t)
        q1: inflow_ktcmd(t)
        q2: rainfall_roll3(t)
        q3: rainfall_mm(t)

    Target:
        water_level_m(t + horizon_days)

    Architecture:
        - 4 qubits (|0000> initial state)
        - L = 2 variational layers with data re-uploading
        - Encoding: Ry(x_tilde) per qubit
        - Variational: Rz(theta) followed by Rx(phi) (16 trainable parameters)
        - Entanglement: Circular CNOT ring (0->1, 1->2, 2->3, 3->0)
        - Readout: <Z0> in [-1, 1]
        - Output: y_hat = w * <Z0> + b (affine scaling to river water level in meters)

Mathematical reference: QML_FORECASTING_DESIGN_REPORT.md
"""
import time
import numpy as np
import pandas as pd
from typing import Optional, List, Tuple, Dict, Any
from scipy.optimize import minimize

from app.quantum.qml_config import QmlConfig, APPROVED_QML_FEATURES
from app.quantum.qml_result import QmlForecastResult
from app.ml.feature_engineering import build_features
from app.ml.evaluation import evaluate_regression


# =============================================================================
# 1. Pure NumPy Quantum Statevector Circuit Simulator
# =============================================================================

def ry_matrix(theta: float) -> np.ndarray:
    """Single-qubit Ry rotation matrix."""
    half = theta / 2.0
    c = np.cos(half)
    s = np.sin(half)
    return np.array([[c, -s], [s, c]], dtype=complex)


def rz_matrix(theta: float) -> np.ndarray:
    """Single-qubit Rz rotation matrix."""
    half = theta / 2.0
    return np.array([[np.exp(-1j * half), 0.0], [0.0, np.exp(1j * half)]], dtype=complex)


def rx_matrix(theta: float) -> np.ndarray:
    """Single-qubit Rx rotation matrix."""
    half = theta / 2.0
    c = np.cos(half)
    s = -1j * np.sin(half)
    return np.array([[c, s], [s, c]], dtype=complex)


def apply_single_qubit_gate(psi: np.ndarray, gate: np.ndarray, target_qubit: int, n_qubits: int = 4) -> np.ndarray:
    """Applies a 2x2 unitary gate to target_qubit in statevector psi of size 2^n_qubits."""
    psi_tensor = psi.reshape([2] * n_qubits)
    psi_tensor = np.tensordot(gate, psi_tensor, axes=([1], [target_qubit]))
    psi_tensor = np.moveaxis(psi_tensor, 0, target_qubit)
    return psi_tensor.flatten()


def _precompute_cnot_perm(control: int, target: int, n_qubits: int = 4) -> np.ndarray:
    dim = 1 << n_qubits
    perm = np.zeros(dim, dtype=int)
    shift_ctrl = n_qubits - 1 - control
    shift_tgt = n_qubits - 1 - target
    for s in range(dim):
        if (s >> shift_ctrl) & 1:
            perm[s] = s ^ (1 << shift_tgt)
        else:
            perm[s] = s
    return perm


# Precomputed 4-qubit CNOT permutation lookups for instant array indexing
CNOT_01_PERM = _precompute_cnot_perm(0, 1, 4)
CNOT_12_PERM = _precompute_cnot_perm(1, 2, 4)
CNOT_23_PERM = _precompute_cnot_perm(2, 3, 4)
CNOT_30_PERM = _precompute_cnot_perm(3, 0, 4)

# Precomputed Pauli-Z eigenvalues on qubit 0 for instant vector dot-product
Z0_SIGNS = np.array([1.0 if not ((s >> 3) & 1) else -1.0 for s in range(16)], dtype=float)


def apply_cnot_gate(psi: np.ndarray, control: int, target: int, n_qubits: int = 4) -> np.ndarray:
    """
    Applies a CNOT gate using precomputed permutation index arrays.
    """
    if n_qubits == 4:
        if control == 0 and target == 1:
            return psi[CNOT_01_PERM]
        elif control == 1 and target == 2:
            return psi[CNOT_12_PERM]
        elif control == 2 and target == 3:
            return psi[CNOT_23_PERM]
        elif control == 3 and target == 0:
            return psi[CNOT_30_PERM]

    # Fallback general permutation calculation
    perm = _precompute_cnot_perm(control, target, n_qubits)
    return psi[perm]


def simulate_vqr_circuit(x_scaled: np.ndarray, theta: np.ndarray, n_qubits: int = 4, layers: int = 2) -> np.ndarray:
    """
    Simulates the 4-qubit VQR circuit with data re-uploading on a single input vector x_scaled in [0, pi]^4.
    Returns the final complex statevector psi of dimension 16.
    """
    dim = 1 << n_qubits
    # Initial state |0000>
    psi = np.zeros(dim, dtype=complex)
    psi[0] = 1.0

    # theta has shape (layers * n_qubits * 2,) = (2 * 4 * 2) = 16 parameters
    param_idx = 0
    for l in range(layers):
        # 1. Feature encoding (Data re-uploading)
        for q in range(n_qubits):
            ry = ry_matrix(float(x_scaled[q]))
            psi = apply_single_qubit_gate(psi, ry, target_qubit=q, n_qubits=n_qubits)

        # 2. Parameterized variational rotations: Rz(theta) then Rx(phi)
        for q in range(n_qubits):
            rz = rz_matrix(float(theta[param_idx]))
            psi = apply_single_qubit_gate(psi, rz, target_qubit=q, n_qubits=n_qubits)
            param_idx += 1

            rx = rx_matrix(float(theta[param_idx]))
            psi = apply_single_qubit_gate(psi, rx, target_qubit=q, n_qubits=n_qubits)
            param_idx += 1

        # 3. Circular CNOT entanglement ring: (0->1, 1->2, 2->3, 3->0)
        psi = psi[CNOT_01_PERM] if n_qubits == 4 else apply_cnot_gate(psi, 0, 1, n_qubits)
        psi = psi[CNOT_12_PERM] if n_qubits == 4 else apply_cnot_gate(psi, 1, 2, n_qubits)
        psi = psi[CNOT_23_PERM] if n_qubits == 4 else apply_cnot_gate(psi, 2, 3, n_qubits)
        psi = psi[CNOT_30_PERM] if n_qubits == 4 else apply_cnot_gate(psi, 3, 0, n_qubits)

    return psi


def expectation_z0(psi: np.ndarray, n_qubits: int = 4) -> float:
    """
    Calculates the expectation value <Z_0> of Pauli Z on qubit 0.
    In big-endian convention, qubit 0 is the most significant bit.
    Eigenvalue is +1 if bit 0 is 0, and -1 if bit 0 is 1.
    """
    probs = np.abs(psi) ** 2
    if n_qubits == 4:
        return float(np.dot(Z0_SIGNS, probs))

    dim = 1 << n_qubits
    shift_0 = n_qubits - 1
    exp_val = 0.0
    for s in range(dim):
        sign = 1.0 if not ((s >> shift_0) & 1) else -1.0
        exp_val += sign * probs[s]
    return float(exp_val)


# =============================================================================
# 2. Variational Quantum Regressor Class
# =============================================================================

class QuantumVariationalRegressor:
    """
    Scikit-learn compatible 4-qubit Variational Quantum Regressor for time-series forecasting.
    """

    def __init__(self, config: Optional[QmlConfig] = None, horizon_days: int = 1):
        self.config = config or QmlConfig()
        self.horizon_days = horizon_days
        self.feature_names = list(self.config.features)
        self.n_qubits = self.config.n_qubits
        self.layers = self.config.layers
        self.trainable_params_count = self.config.trainable_params_count

        # Scaler attributes (fitted strictly on training data)
        self.feature_mins: Optional[np.ndarray] = None
        self.feature_maxs: Optional[np.ndarray] = None
        self.target_min: Optional[float] = None
        self.target_max: Optional[float] = None

        # Affine output transformation: y_hat = affine_w * <Z0> + affine_b
        self.affine_w: float = 1.0
        self.affine_b: float = 0.0

        # Model weights
        self.parameters: Optional[np.ndarray] = None
        self.is_fitted: bool = False
        self.loss_history: List[float] = []

    def _scale_features(self, X: np.ndarray) -> np.ndarray:
        """Scales raw features into angle range [0, pi] using training parameters."""
        if self.feature_mins is None or self.feature_maxs is None:
            raise RuntimeError("Scaler has not been fitted on training data.")
        denom = np.where(self.feature_maxs - self.feature_mins == 0, 1.0, self.feature_maxs - self.feature_mins)
        scaled = np.pi * (X - self.feature_mins) / denom
        return np.clip(scaled, 0.0, np.pi)

    def _predict_raw_expectations(self, X_scaled: np.ndarray, theta: np.ndarray) -> np.ndarray:
        """Evaluates <Z0> for each row in X_scaled."""
        n_samples = len(X_scaled)
        expectations = np.zeros(n_samples, dtype=float)
        for i in range(n_samples):
            psi = simulate_vqr_circuit(X_scaled[i], theta, n_qubits=self.n_qubits, layers=self.layers)
            expectations[i] = expectation_z0(psi, n_qubits=self.n_qubits)
        return expectations

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "QuantumVariationalRegressor":
        """
        Fits feature scaler and variational parameters using COBYLA optimizer.
        Ensures strict chronological isolation (scaler fitted strictly on provided X, y).
        """
        # Validate feature columns
        missing = [f for f in self.feature_names if f not in X.columns]
        if missing:
            raise ValueError(f"Input features missing required columns: {missing}")

        X_mat = X[self.feature_names].to_numpy(dtype=float)
        y_vec = y.to_numpy(dtype=float)

        # Handle edge cases
        if len(X_mat) < 10:
            raise ValueError("Training requires at least 10 samples.")
        if np.any(np.isnan(X_mat)) or np.any(np.isnan(y_vec)):
            raise ValueError("Training data contains NaN values.")

        # 1. Fit MinMax Scaler parameters strictly on training features
        self.feature_mins = np.min(X_mat, axis=0)
        self.feature_maxs = np.max(X_mat, axis=0)
        self.target_min = float(np.min(y_vec))
        self.target_max = float(np.max(y_vec))

        # Default affine mapping centered in physical water-level domain
        self.affine_w = (self.target_max - self.target_min) / 2.0
        self.affine_b = (self.target_max + self.target_min) / 2.0
        if abs(self.affine_w) < 1e-6:
            self.affine_w = 1.0

        X_scaled = self._scale_features(X_mat)

        # Subsample for interactive response if requested
        if self.config.train_subsample and len(X_scaled) > self.config.train_subsample:
            # Use most recent continuous chronological segment of training window
            X_train_opt = X_scaled[-self.config.train_subsample:]
            y_train_opt = y_vec[-self.config.train_subsample:]
        else:
            X_train_opt = X_scaled
            y_train_opt = y_vec

        # Initialize variational angles reproducibly
        rng = np.random.default_rng(self.config.seed)
        init_theta = rng.uniform(-np.pi / 4.0, np.pi / 4.0, size=self.trainable_params_count)

        self.loss_history = []

        def objective(theta: np.ndarray) -> float:
            exp_vals = self._predict_raw_expectations(X_train_opt, theta)
            # Closed-form OLS calibration of affine parameters (w, b)
            # Fits y_hat = w * <Z0> + b
            z_mean = np.mean(exp_vals)
            y_mean = np.mean(y_train_opt)
            var_z = np.var(exp_vals)
            if var_z > 1e-8:
                cov_zy = np.mean((exp_vals - z_mean) * (y_train_opt - y_mean))
                w = cov_zy / var_z
                b = y_mean - w * z_mean
            else:
                w = self.affine_w
                b = self.affine_b

            preds = w * exp_vals + b
            mse = float(np.mean((preds - y_train_opt) ** 2))
            reg = 1e-4 * float(np.sum(theta ** 2))
            loss = mse + reg
            self.loss_history.append(loss)
            return loss

        # Run classical COBYLA optimizer
        opt_res = minimize(
            objective,
            init_theta,
            method=self.config.optimizer_method,
            options={"maxiter": self.config.max_iter, "tol": self.config.tolerance},
        )

        self.parameters = opt_res.x

        # Calibrate final affine parameters w and b on full training set
        final_exp = self._predict_raw_expectations(X_scaled, self.parameters)
        z_mean = np.mean(final_exp)
        y_mean = np.mean(y_vec)
        var_z = np.var(final_exp)
        if var_z > 1e-8:
            cov_zy = np.mean((final_exp - z_mean) * (y_vec - y_mean))
            self.affine_w = float(cov_zy / var_z)
            self.affine_b = float(y_mean - self.affine_w * z_mean)

        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generates continuous water-level predictions for input features X."""
        if not self.is_fitted or self.parameters is None:
            raise RuntimeError("QuantumVariationalRegressor must be fitted before calling predict().")

        missing = [f for f in self.feature_names if f not in X.columns]
        if missing:
            raise ValueError(f"Input features missing required columns: {missing}")

        X_mat = X[self.feature_names].to_numpy(dtype=float)
        X_scaled = self._scale_features(X_mat)
        raw_exp = self._predict_raw_expectations(X_scaled, self.parameters)
        preds = self.affine_w * raw_exp + self.affine_b
        return np.round(preds, 3)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluates MAE, RMSE, and R2 on a test split."""
        preds = self.predict(X)
        return evaluate_regression(y.to_numpy(), preds)


# =============================================================================
# 3. High-Level QML Pipeline Execution & Forecasting Helpers
# =============================================================================

def prepare_qml_data(df: pd.DataFrame, horizon_days: int = 1, test_fraction: float = 0.2):
    """
    Prepares chronological training and testing data specifically for the 4 approved QML features.
    Guarantees strict chronological ordering with zero temporal leakage.
    """
    if horizon_days < 1:
        raise ValueError(f"horizon_days must be >= 1 (got {horizon_days}).")

    working = df.copy()
    shifted_target_col = "water_level_m_target"
    working[shifted_target_col] = working["water_level_m"].shift(-horizon_days)
    working = working.dropna(subset=[shifted_target_col]).reset_index(drop=True)

    # Use existing feature engineering to construct rolling features
    engineered, _ = build_features(working, shifted_target_col)

    # Extract exactly the 4 approved QML features in fixed deterministic order
    X = engineered[APPROVED_QML_FEATURES]
    y = engineered[shifted_target_col]
    dates = engineered["date"]

    # Chronological split
    n = len(X)
    split_idx = int(n * (1.0 - test_fraction))
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    dates_train, dates_test = dates.iloc[:split_idx], dates.iloc[split_idx:]

    return X_train, X_test, y_train, y_test, dates_train, dates_test


def train_and_evaluate_qml(
    df: pd.DataFrame,
    horizon_days: int = 1,
    config: Optional[QmlConfig] = None,
) -> Tuple[QuantumVariationalRegressor, QmlForecastResult]:
    """
    Trains and evaluates the Quantum Variational Regressor end-to-end.
    """
    if len(df) < 60:
        raise ValueError("Not enough data to train (need at least 60 rows).")

    cfg = config or QmlConfig()
    X_train, X_test, y_train, y_test, dates_train, dates_test = prepare_qml_data(
        df, horizon_days=horizon_days, test_fraction=0.2
    )

    model = QuantumVariationalRegressor(config=cfg, horizon_days=horizon_days)

    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    training_time_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    test_preds = model.predict(X_test)
    inference_time_ms = (time.perf_counter() - t1) * 1000.0

    metrics = evaluate_regression(y_test.to_numpy(), test_preds)

    predictions = [
        {
            "date": pd.Timestamp(d).strftime("%Y-%m-%d"),
            "actual": round(float(a), 3),
            "predicted": round(float(p), 3),
        }
        for d, a, p in zip(dates_test, y_test, test_preds)
    ]

    scaling_params = {
        "feature_mins": {f: round(float(m), 4) for f, m in zip(model.feature_names, model.feature_mins)},
        "feature_maxs": {f: round(float(m), 4) for f, m in zip(model.feature_names, model.feature_maxs)},
        "target_min": round(float(model.target_min), 4),
        "target_max": round(float(model.target_max), 4),
    }

    result = QmlForecastResult(
        engine_type="quantum_vqr",
        model_name="quantum_variational_regressor",
        horizon_days=horizon_days,
        train_size=len(X_train),
        test_size=len(X_test),
        qubits=cfg.n_qubits,
        circuit_depth_layers=cfg.layers,
        trainable_parameters_count=cfg.trainable_params_count,
        optimal_parameters=[float(p) for p in model.parameters],
        metrics=metrics,
        predictions=predictions,
        feature_names=APPROVED_QML_FEATURES,
        training_time_ms=training_time_ms,
        inference_time_ms=inference_time_ms,
        simulator_name="Pure NumPy Statevector",
        training_loss_history=[round(float(l), 6) for l in model.loss_history[-20:]],
        scaling_params=scaling_params,
        affine_w=model.affine_w,
        affine_b=model.affine_b,
        metadata={
            "optimizer": cfg.optimizer_method,
            "max_iter": cfg.max_iter,
            "random_seed": cfg.seed,
            "data_reuploading": True,
            "qubit_mapping": {f"q{i}": feat for i, feat in enumerate(APPROVED_QML_FEATURES)},
        },
    )

    return model, result


def predict_next_qml(
    model: QuantumVariationalRegressor,
    df: pd.DataFrame,
    horizon_days: int = 1,
) -> Dict[str, Any]:
    """
    Generates a single forward forecast for day t + horizon_days using the latest available observation.
    Maintains compatibility with downstream risk generation.
    """
    if not model.is_fitted:
        raise RuntimeError("QML Model must be trained before calling predict_next_qml().")

    # Use feature engineering on historical data
    engineered, _ = build_features(df, "dummy_target")
    latest_row = engineered[APPROVED_QML_FEATURES].iloc[[-1]]
    latest_date = engineered["date"].iloc[-1]

    pred_val = float(model.predict(latest_row)[0])
    last_known = df.iloc[-1]

    return {
        "based_on_date": pd.Timestamp(latest_date).strftime("%Y-%m-%d"),
        "horizon_days": horizon_days,
        "predicted_water_level_m": round(pred_val, 3),
        "last_known_rainfall_mm": round(float(last_known["rainfall_mm"]), 2),
        "last_known_inflow_ktcmd": round(float(last_known["inflow_ktcmd"]), 2),
        "last_known_water_level_m": round(float(last_known["water_level_m"]), 3),
        "model_used": "quantum_variational_regressor",
        "engine_type": "quantum_vqr",
        "qubits": model.n_qubits,
        "qubit_count": model.n_qubits,
        "circuit_depth": model.config.circuit_depth,
    }


def evaluate_qml_multiseed(
    df: pd.DataFrame,
    horizon_days: int = 1,
    seeds: Optional[List[int]] = None,
    max_iter: int = 30,
    train_subsample: int = 100,
) -> Dict[str, Any]:
    """
    Evaluates the 4-qubit VQR across multiple deterministic random seeds (Target B Step 4)
    to establish statistical robustness without cherry-picking.
    """
    if seeds is None:
        seeds = [42, 123, 777, 2026]

    runs = []
    r2_scores = []
    mae_scores = []
    rmse_scores = []

    for seed in seeds:
        cfg = QmlConfig(
            n_qubits=4,
            layers=2,
            max_iter=max_iter,
            train_subsample=train_subsample,
            seed=seed,
        )
        t0 = time.perf_counter()
        model, result = train_and_evaluate_qml(df=df, horizon_days=horizon_days, config=cfg)
        elapsed = round(time.perf_counter() - t0, 3)

        r2 = result.test_r2
        mae = result.test_mae
        rmse = result.test_rmse

        runs.append({
            "seed": seed,
            "r2": round(r2, 4),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "runtime_s": elapsed,
        })
        r2_scores.append(r2)
        mae_scores.append(mae)
        rmse_scores.append(rmse)

    return {
        "seeds_evaluated": seeds,
        "runs": runs,
        "summary": {
            "mean_r2": round(float(np.mean(r2_scores)), 4),
            "std_r2": round(float(np.std(r2_scores)), 4),
            "best_r2": round(float(np.max(r2_scores)), 4),
            "worst_r2": round(float(np.min(r2_scores)), 4),
            "mean_mae": round(float(np.mean(mae_scores)), 4),
            "std_mae": round(float(np.std(mae_scores)), 4),
            "best_mae": round(float(np.min(mae_scores)), 4),
            "worst_mae": round(float(np.max(mae_scores)), 4),
            "mean_rmse": round(float(np.mean(rmse_scores)), 4),
            "std_rmse": round(float(np.std(rmse_scores)), 4),
        },
        "academic_conclusion": (
            f"Multi-seed evaluation demonstrates repeatable functional quantum regression "
            f"(mean R2 = {np.mean(r2_scores):.4f} +/- {np.std(r2_scores):.4f}). "
            f"Classical tree and linear baselines remain superior on this dataset."
        ),
    }
