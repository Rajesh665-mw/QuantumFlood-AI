# QuantumFlood AI — Hybrid Quantum-Classical System Architecture & Formulation Specification

## 1. Executive Summary & Scientific Honesty Policy

**QuantumFlood AI** is a hybrid quantum-classical flood forecasting and disaster response decision-support system. In accordance with rigorous scientific standards:
1. **Simulation Fidelity**: All quantum algorithms execute on local, deterministic quantum statevector and shot-based circuit simulators in pure NumPy and SciPy. No physical quantum hardware claims are made.
2. **No Fabricated Advantage**: Classical algorithms (Greedy Set Cover, Gradient Boosted Trees, Linear Programming) serve as verified baselines. Quantum methods are evaluated honestly; classical baselines frequently outperform small-scale quantum simulators on noisy or limited real-world datasets.
3. **Operational Protection**: Quantum optimization recommendations never bypass classical deterministic safeguards (warehouse inventory conservation, road network reachability, and shelter capacity verification).
4. **Transparent Provenance**: Every API response identifies the exact solver engine (`classical_greedy`, `quantum_qaoa`, `classical_mcda`, `quantum_vqr`), simulation parameters, execution latency, and feasibility status.

---

## 2. Mathematical Formulations & Complexity Analysis

### 2.1 Problem 1: Smart Sensor Placement (Weighted Maximum Coverage)
- **Classical Formulation**:
  Let $C = \{c_1, \dots, c_N\}$ be candidate sensor locations, $Z = \{z_1, \dots, z_M\}$ be risk zones, and $K$ be the sensor budget.
  Zone objective weights $w_z = \text{risk\_score}_z \times \mu_z$ (where $\mu_z = 2.0$ for `CRITICAL` zones).
  Coverage matrix $A \in \{0, 1\}^{M \times N}$, where $A_{z, j} = 1 \iff \text{dist}(z, c_j) \le R_{\text{cov}}$.
  The Weighted Maximum Coverage Problem is NP-hard. Classical greedy approximation guarantees a $(1 - 1/e) \approx 63.2\%$ approximation ratio.
- **QUBO / Ising Encoding**:
  Decision variables: $x_j \in \{0, 1\}$ for each candidate $j \in \{0, \dots, N-1\}$.
  Pairwise coverage truncation:
  $$\text{Coverage}(x) = \sum_{j=0}^{N-1} \alpha_j x_j - \sum_{0 \le j < k < N} \beta_{jk} x_j x_k$$
  where $\alpha_j = \sum_{z \in \text{Cov}(c_j)} w_z$ and $\beta_{jk} = \sum_{z \in \text{Cov}(c_j) \cap \text{Cov}(c_k)} w_z$.
  Spatial separation constraint (preventing clustering within $d_{\text{min}}$):
  $$H_{\text{dist}}(x) = P_{\text{dist}} \sum_{\text{dist}(c_j, c_k) < d_{\text{min}}} x_j x_k$$
  Budget constraint:
  $$H_{\text{budget}}(x) = P_{\text{budget}} \left(\sum_{j=0}^{N-1} x_j - K\right)^2$$
  Total QUBO Hamiltonian to minimize:
  $$H(x) = -\text{Coverage}(x) + H_{\text{dist}}(x) + H_{\text{budget}}(x) = x^T Q x + \text{offset}$$
  Analytically safe penalty: $P_{\text{budget}} > \max_j(\alpha_j)$.
- **QAOA Circuit & Statevector Simulation**:
  Depth $p$: Alternating cost unitary $U(H_C, \gamma_l) = \exp(-i \gamma_l H_C)$ (diagonal phase rotation) and mixer unitary $U(H_M, \beta_l) = \exp(-i \beta_l \sum_j X_j)$ (single-qubit $R_x(2\beta_l)$).
  Classical parameter optimization via COBYLA minimizes expectation $\langle \psi(\gamma, \beta) | H_C | \psi(\gamma, \beta) \rangle$.
  Measurement sampling produces candidate bitstrings, followed by deterministic priority-guided feasibility repair if $\sum x_j \ne K$.

---

### 2.2 Problem 2: Hydrological Flood Forecasting (Variational Quantum Regressor)
- **Classical Baseline**:
  Chronologically trained Ridge Regression, Random Forest, and Gradient Boosting Regressors on lagged river levels, rolling 3-day rainfall, and reservoir inflow.
- **Quantum Machine Learning (QML) Formulation**:
  4-qubit parameterized quantum circuit with data re-uploading ($L=2$ variational layers):
  1. *Encoding*: $R_y(\tilde{x}_q)$ where $\tilde{x}_q = \pi \frac{x_q - \min(x_q)}{\max(x_q) - \min(x_q)}$ on qubit $q \in \{0, 1, 2, 3\}$.
  2. *Parameterized Rotations*: $R_z(\theta_{l, q}) R_x(\phi_{l, q})$ (16 trainable classical parameters).
  3. *Entanglement*: Circular CNOT topology $(0 \to 1, 1 \to 2, 2 \to 3, 3 \to 0)$.
  4. *Readout*: Expectation value $\langle Z_0 \rangle \in [-1, 1]$ on qubit 0.
  5. *Affine Mapping*: $\hat{y} = w \langle Z_0 \rangle + b$.
  6. *Uncertainty Calibration*: Calibrated confidence interval $[\hat{y} - 1.96 \sigma_{\text{res}}, \hat{y} + 1.96 \sigma_{\text{res}}]$ using test residual standard deviation and shot variance.

---

### 2.3 Problem 3: Shelter Site Selection Portfolio Optimization
- **Classical Baseline**:
  Multi-Criteria Decision Analysis (MCDA) scoring each candidate site independently based on elevation, river distance, road accessibility, and zone flood risk.
- **Quantum / Hybrid Formulation**:
  Selecting a portfolio of $K_{\text{shelter}}$ proposed sites from $S_{\text{cand}}$ candidates to maximize collective suitability while penalizing spatial proximity clustering:
  $$H_{\text{shelter}}(y) = -\sum_{s=1}^S \text{Suitability}_s y_s + \lambda_{\text{disp}} \sum_{s < s'} \max\left(0, 1 - \frac{\text{dist}(s, s')}{d_{\text{min}}}\right) y_s y_{s'} + P_{\text{shelter}} \left(\sum_{s=1}^S y_s - K_{\text{shelter}}\right)^2$$
  where $y_s \in \{0, 1\}$. Solved via QUBO matrix diagonalization / QAOA statevector simulation, compared against classical greedy and exact branch-and-bound.

---

### 2.4 Problem 4: Emergency Resource Allocation across Shelter Requests
- **Classical Baseline**:
  First-come, first-served or priority-ordered greedy allocation.
- **Quantum / Hybrid Formulation**:
  Discrete allocation options $x_{r, l} \in \{0, 1\}$ for each pending shelter request $r$ and discrete fulfillment fraction $l \in \{25\%, 50\%, 75\%, 100\%\}$:
  $$\max \sum_{r} \sum_{l} \text{Urgency}_r \times \text{Qty}_{r, l} \times x_{r, l} - \lambda_{\text{unmet}} \sum_r (\text{Requested}_r - \text{Allocated}_r)^2$$
  subject to strictly one fulfillment option per request $\sum_l x_{r, l} \le 1$ and warehouse inventory constraint $\sum_r \text{Allocated}_r \le \text{AvailableStock}$.
  Encodable as a constrained QUBO for small request batches ($N \le 16$ binary decision variables), with guaranteed classical inventory conservation fallback.

---

## 3. Provenance and Solver Metadata Schema

All solver results expose the standardized schema:
```json
{
  "solver_used": "quantum_qaoa | classical_greedy | classical_mcda | quantum_portfolio",
  "execution_mode": "hybrid_simulator | classical_baseline",
  "backend_name": "numpy_statevector_simulator | scipy_cobyla",
  "total_qubits": 10,
  "circuit_depth": 3,
  "shots": 1024,
  "objective_value": 48.75,
  "is_feasible": true,
  "constraint_violations": 0,
  "execution_time_ms": 142.5,
  "classical_baseline_comparison": {
    "baseline_solver": "classical_greedy",
    "baseline_objective": 49.20,
    "relative_difference_pct": -0.91,
    "observation": "Classical greedy achieved comparable coverage with lower computational overhead."
  }
}
```
