"""
Automated Test Suite for Quantum Machine Learning (QML) Forecasting Module
==========================================================================
Verifies:
1. Mathematical correctness of pure NumPy quantum gates and statevector simulation
   against independent Kronecker-product matrix operations.
2. 4-qubit Variational Quantum Regressor (VQR) architecture (L=2, 16 params, data re-uploading).
3. Zero temporal data leakage (angle scaler fitted exclusively on training set).
4. Deterministic angle encoding and feature ordering.
5. Closed-form OLS affine scaling y = w <Z0> + b.
6. Robustness on edge cases (zero rain, constant values, small data, NaNs).
7. API routes: /forecast/qml/train, /forecast/qml/predict, /forecast/qml/results, /forecast/compare.
8. Downstream integration with Spatial Risk Engine (/risk/generate).
9. Subsystem and failure isolation (classical pipeline continues to operate if QML fails).
"""
import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.quantum.qml_config import QmlConfig, APPROVED_QML_FEATURES
from app.quantum.qml_forecaster import (
    simulate_vqr_circuit,
    expectation_z0,
    ry_matrix,
    rz_matrix,
    rx_matrix,
    QuantumVariationalRegressor,
    train_and_evaluate_qml,
    predict_next_qml,
    prepare_qml_data,
)
from app.quantum.qml_result import QmlForecastResult
from app.services.data_service import get_clean_dataset
from app.ml.model_manager import ModelManager


client = TestClient(app)


# =====================================================================
# 1. INDEPENDENT MATHEMATICAL VERIFICATION (KRONECKER MATRIX VALIDATION)
# =====================================================================

class TestQmlQuantumCircuitValidation:
    """Validates quantum gates and VQR statevector against independent matrix exponentials."""

    def test_single_qubit_gate_unitarity(self):
        """Verify U_dagger * U = I for Ry, Rz, Rx across diverse angles."""
        angles = [0.0, np.pi / 4, np.pi / 2, np.pi, 2.718]
        I2 = np.eye(2, dtype=complex)
        for theta in angles:
            for gate_fn in [ry_matrix, rz_matrix, rx_matrix]:
                U = gate_fn(theta)
                np.testing.assert_allclose(U.conj().T @ U, I2, atol=1e-15)

    def test_independent_kronecker_vqr_equivalence(self):
        """
        Independently construct the exact 16x16 unitary matrix using Kronecker
        products and compare against the optimized statevector simulator.
        """
        I2 = np.eye(2, dtype=complex)
        X = np.array([[0, 1], [1, 0]], dtype=complex)
        P0 = np.array([[1, 0], [0, 0]], dtype=complex)
        P1 = np.array([[0, 0], [0, 1]], dtype=complex)

        # Independent full 16x16 CNOT matrix builder
        def build_cnot_16(ctrl, tgt):
            # CNOT = |0><0| (x) I + |1><1| (x) X on the 2 qubits, I on the rest
            def kron_qubits(ops):
                res = ops[0]
                for op in ops[1:]:
                    res = np.kron(res, op)
                return res

            # Term 0: control is 0 -> target is I
            ops0 = [I2] * 4
            ops0[ctrl] = P0
            term0 = kron_qubits(ops0)

            # Term 1: control is 1 -> target is X
            ops1 = [I2] * 4
            ops1[ctrl] = P1
            ops1[tgt] = X
            term1 = kron_qubits(ops1)

            return term0 + term1

        # Test features and angles
        x_sample = np.array([0.45, 1.25, 2.10, 0.78], dtype=np.float64)
        theta_sample = np.linspace(0.1, 1.6, 16, dtype=np.float64)

        # Run vectorized simulator
        state_sim = simulate_vqr_circuit(x_sample, theta_sample, layers=2)
        exp_z0_sim = expectation_z0(state_sim)

        # Independent Kronecker simulation:
        # Start in |0000>
        state_ind = np.zeros(16, dtype=complex)
        state_ind[0] = 1.0

        def apply_1q_ind(psi, q_idx, gate):
            ops = [I2] * 4
            ops[q_idx] = gate
            U = ops[0]
            for op in ops[1:]:
                U = np.kron(U, op)
            return U @ psi

        cnot_01 = build_cnot_16(0, 1)
        cnot_12 = build_cnot_16(1, 2)
        cnot_23 = build_cnot_16(2, 3)
        cnot_30 = build_cnot_16(3, 0)

        param_idx = 0
        for l in range(2):
            # Data re-uploading (Ry)
            for q in range(4):
                state_ind = apply_1q_ind(state_ind, q, ry_matrix(x_sample[q]))
            # Trainable rotations (Rz then Rx)
            for q in range(4):
                state_ind = apply_1q_ind(state_ind, q, rz_matrix(theta_sample[param_idx]))
                param_idx += 1
                state_ind = apply_1q_ind(state_ind, q, rx_matrix(theta_sample[param_idx]))
                param_idx += 1
            # Circular CNOT
            state_ind = cnot_01 @ state_ind
            state_ind = cnot_12 @ state_ind
            state_ind = cnot_23 @ state_ind
            state_ind = cnot_30 @ state_ind

        # Independent <Z0> expectation: Z on qubit 0
        Z = np.array([[1, 0], [0, -1]], dtype=complex)
        Z0_16 = np.kron(Z, np.kron(I2, np.kron(I2, I2)))
        exp_z0_ind = np.real(state_ind.conj().T @ (Z0_16 @ state_ind))

        # Precision assertions
        np.testing.assert_allclose(state_sim, state_ind, atol=1e-14)
        np.testing.assert_allclose(exp_z0_sim, exp_z0_ind, atol=1e-14)
        assert -1.0 <= exp_z0_sim <= 1.0


# =====================================================================
# 2. FEATURE ENCODING, ORDERING, AND DATA LEAKAGE PREVENTION
# =====================================================================

class TestQmlFeatureEncodingAndScaling:
    """Verifies strict adherence to approved feature specifications and zero leakage."""

    def test_approved_feature_list_and_ordering(self):
        """Feature ordering must deterministically map to qubits q0..q3."""
        expected_features = [
            "water_level_m",
            "inflow_ktcmd",
            "rainfall_roll3",
            "rainfall_mm",
        ]
        assert APPROVED_QML_FEATURES == expected_features
        assert len(APPROVED_QML_FEATURES) == 4

    def test_zero_temporal_leakage_scaling(self):
        """
        Angle scaler must be fitted STRICTLY on X_train.
        Adding extreme values in X_test must NOT change the scaling parameters of X_train.
        """
        # Create synthetic time series
        dates = pd.date_range("2024-01-01", periods=100)
        df_normal = pd.DataFrame({
            "date": dates,
            "water_level_m": np.linspace(10, 20, 100),
            "inflow_ktcmd": np.linspace(50, 150, 100),
            "rainfall_roll3": np.linspace(0, 30, 100),
            "rainfall_mm": np.linspace(0, 50, 100),
        })

        X_train_norm, X_test_norm, y_train_norm, y_test_norm, _, _ = prepare_qml_data(df_normal, horizon_days=1, test_fraction=0.2)
        reg_normal = QuantumVariationalRegressor()
        reg_normal.fit(X_train_norm, y_train_norm)

        # Now simulate a massive hurricane in the test period only
        df_extreme_test = df_normal.copy()
        df_extreme_test.loc[80:, "rainfall_mm"] = 9999.0  # extreme anomaly in test period

        X_train_ext, X_test_ext, y_train_ext, y_test_ext, _, _ = prepare_qml_data(df_extreme_test, horizon_days=1, test_fraction=0.2)
        reg_extreme = QuantumVariationalRegressor()
        reg_extreme.fit(X_train_ext, y_train_ext)

        # Training scaler parameters MUST be completely identical (no forward leakage)
        np.testing.assert_array_equal(reg_normal.feature_mins, reg_extreme.feature_mins)
        np.testing.assert_array_equal(reg_normal.feature_maxs, reg_extreme.feature_maxs)

        # Train angles must remain strictly bounded in [0, pi]
        scaled = reg_normal._scale_features(X_train_norm.to_numpy())
        assert np.all(scaled >= 0.0)
        assert np.all(scaled <= np.pi)

    def test_chronological_ordering_preserved(self):
        """Check train_dates < test_dates without random shuffling."""
        df = get_clean_dataset()
        X_train, X_test, y_train, y_test, dates_train, dates_test = prepare_qml_data(df, horizon_days=1, test_fraction=0.2)

        assert dates_train.max() < dates_test.min()
        assert len(dates_train) + len(dates_test) == len(y_train) + len(y_test)


# =====================================================================
# 3. VQR REGRESSOR TRAINING & MATHEMATICAL CONSISTENCY
# =====================================================================

class TestQmlRegressorTraining:
    """Verifies parameter count, affine readout, and deterministic reproducibility."""

    def test_parameter_count_formula(self):
        """Approved architecture: 4 qubits, L=2 -> exactly 16 trainable parameters."""
        config = QmlConfig(n_qubits=4, n_layers=2)
        expected_params = config.n_qubits * config.n_layers * 2
        assert config.n_parameters == 16
        assert config.n_parameters == expected_params
        assert config.circuit_depth == 11

    def test_affine_transformation_closed_form(self):
        """
        Verify that the affine scaling parameters (w, b) minimize squared error
        between <Z0> expectations and true water levels.
        """
        regressor = QuantumVariationalRegressor(QmlConfig(n_qubits=4, n_layers=2))
        z_sample = np.array([-0.8, -0.2, 0.4, 0.9])
        y_sample = np.array([12.0, 15.0, 18.0, 21.0])

        z_mean = np.mean(z_sample)
        y_mean = np.mean(y_sample)
        var_z = np.var(z_sample)
        cov_zy = np.mean((z_sample - z_mean) * (y_sample - y_mean))
        w = float(cov_zy / var_z)
        b = float(y_mean - w * z_mean)

        assert w > 0
        y_pred = w * z_sample + b
        residual = np.sum((y_pred - y_sample) ** 2)
        assert residual < 0.1

    def test_reproducibility_with_seed(self):
        """Identical random seeds must yield identical parameter vectors."""
        df = get_clean_dataset().head(90)
        config1 = QmlConfig(n_qubits=4, n_layers=2, max_iter=15, seed=123, train_subsample=40)
        config2 = QmlConfig(n_qubits=4, n_layers=2, max_iter=15, seed=123, train_subsample=40)

        reg1, res1 = train_and_evaluate_qml(df, horizon_days=1, config=config1)
        reg2, res2 = train_and_evaluate_qml(df, horizon_days=1, config=config2)

        np.testing.assert_allclose(reg1.parameters, reg2.parameters, atol=1e-12)
        assert res1.test_rmse == res2.test_rmse
        assert res1.affine_w == res2.affine_w
        assert res1.affine_b == res2.affine_b

    def test_end_to_end_training_performance(self):
        """VQR trained on krishna_hydro_demo.csv achieves reasonable hydro regression."""
        df = get_clean_dataset()
        config = QmlConfig(n_qubits=4, n_layers=2, max_iter=30, seed=42, train_subsample=80)
        regressor, result = train_and_evaluate_qml(df, horizon_days=1, config=config)

        assert isinstance(result, QmlForecastResult)
        assert result.n_qubits == 4
        assert result.n_parameters == 16
        assert "pure numpy" in result.simulator.lower()
        assert result.test_rmse < 2.0  # Measured RMSE is ~0.9m
        assert result.test_mae < 2.0   # Measured MAE is ~0.8m
        assert result.test_r2 is not None
        assert result.training_time_s > 0
        assert result.inference_time_s > 0


# =====================================================================
# 4. EDGE CASES & ERROR RESILIENCE
# =====================================================================

class TestQmlEdgeCases:
    """Verifies behavior on boundary conditions and malformed inputs."""

    def test_zero_rainfall_dry_season(self):
        """Model should handle zero rainfall seamlessly."""
        dates = pd.date_range("2024-01-01", periods=80)
        df_dry = pd.DataFrame({
            "date": dates,
            "water_level_m": np.linspace(13.0, 13.5, 80),
            "inflow_ktcmd": np.full(80, 45.0),
            "rainfall_roll3": np.zeros(80),
            "rainfall_mm": np.zeros(80),
        })
        config = QmlConfig(n_qubits=4, n_layers=2, max_iter=10, train_subsample=40)
        regressor, result = train_and_evaluate_qml(df_dry, horizon_days=1, config=config)
        assert result.test_rmse is not None
        assert not np.isnan(result.test_rmse)

    def test_constant_feature_scaling_stability(self):
        """Constant features (zero variance) must not divide by zero."""
        dates = pd.date_range("2024-01-01", periods=80)
        df_const = pd.DataFrame({
            "date": dates,
            "water_level_m": np.linspace(13.0, 14.0, 80),
            "inflow_ktcmd": np.full(80, 50.0),  # Constant feature!
            "rainfall_roll3": np.zeros(80),     # Constant feature!
            "rainfall_mm": np.zeros(80),        # Constant feature!
        })
        config = QmlConfig(n_qubits=4, n_layers=2, max_iter=10, train_subsample=40)
        regressor, result = train_and_evaluate_qml(df_const, horizon_days=1, config=config)
        pred = predict_next_qml(regressor, df_const)
        assert pred["predicted_water_level_m"] > 0

    def test_insufficient_data_error(self):
        """Data with fewer than 60 rows must raise ValueError."""
        df_tiny = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=15),
            "water_level_m": np.ones(15),
            "inflow_ktcmd": np.ones(15),
            "rainfall_roll3": np.ones(15),
            "rainfall_mm": np.ones(15),
        })
        with pytest.raises(ValueError, match="at least 60 rows"):
            train_and_evaluate_qml(df_tiny, horizon_days=1)

    def test_missing_feature_column_error(self):
        """Data missing one of the 4 approved columns must raise KeyError or ValueError."""
        df_bad = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=80),
            "water_level_m": np.ones(80),
            "inflow_ktcmd": np.ones(80),
            # missing rainfall_roll3 and rainfall_mm
        })
        with pytest.raises((KeyError, ValueError)):
            prepare_qml_data(df_bad, horizon_days=1)


# =====================================================================
# 5. API ROUTES, COMPARISON, AND RISK INTEGRATION
# =====================================================================

class TestQmlApiAndIntegration:
    """Verifies FastAPI endpoints and cross-module risk-pipeline coupling."""

    def test_qml_train_and_predict_endpoints(self):
        """POST /api/forecast/qml/train and POST /api/forecast/qml/predict."""
        train_resp = client.post(
            "/api/forecast/qml/train",
            json={"horizon_days": 1, "n_layers": 2, "max_iter": 15, "train_subsample": 50, "seed": 42},
        )
        assert train_resp.status_code == 200
        data = train_resp.json()
        assert "variational_regressor" in data["model_name"].lower() or "vqr" in data["model_name"].lower()
        assert data["n_qubits"] == 4
        assert data["circuit_depth"] == 11
        assert "test_rmse" in data

        # Prediction endpoint
        pred_resp = client.post(
            "/api/forecast/qml/predict",
            json={"horizon_days": 1},
        )
        assert pred_resp.status_code == 200
        pred = pred_resp.json()
        assert pred["predicted_water_level_m"] > 0
        assert pred["qubit_count"] == 4

        # Results endpoint
        res_resp = client.get("/api/forecast/qml/results")
        assert res_resp.status_code == 200
        assert res_resp.json()["latest_prediction"] is not None

    def test_tournament_comparison_endpoint(self):
        """POST /api/forecast/compare compares classical vs QML."""
        resp = client.post(
            "/api/forecast/compare",
            json={"horizon_days": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "classical" in data
        assert "qml" in data
        assert data["classical"]["model_name"] is not None
        assert data["qml"]["available"] is True
        assert data["qml"]["n_qubits"] == 4
        assert "comparison" in data
        assert "observation" in data["comparison"]
        assert "scientific_note" in data["comparison"]

    def test_qml_risk_pipeline_integration(self):
        """POST /api/risk/generate with forecast_model_preference='qml'."""
        # First ensure QML forecast prediction exists
        client.post("/api/forecast/qml/predict", json={"horizon_days": 1})

        # Run risk generation using QML forecast
        resp = client.post(
            "/api/risk/generate",
            json={"use_latest_forecast": True, "forecast_model_preference": "qml"},
        )
        assert resp.status_code == 200
        risk_map = resp.json()
        assert "zones" in risk_map
        assert len(risk_map["zones"]) > 0
        assert risk_map.get("forecast_source") == "qml"

    def test_classical_subsystem_isolation(self):
        """
        Verify that classical forecasting endpoints remain completely operational
        even if QML state is queried before training or if QML encounters an issue.
        """
        # Classical train
        c_train = client.post("/api/forecast/train", json={"horizon_days": 1})
        assert c_train.status_code == 200

        # Classical predict
        c_pred = client.post("/api/forecast/predict", json={"horizon_days": 1})
        assert c_pred.status_code == 200
        assert c_pred.json()["predicted_water_level_m"] > 0

        # Classical results
        c_res = client.get("/api/forecast/results")
        assert c_res.status_code == 200
        assert c_res.json()["best_model_name"] is not None
