# QuantumFlood AI — Mathematical Formulations Reference

> **Document Purpose:** Consolidated reference for all mathematical models, algorithms,
> and optimality guarantees used in the QuantumFlood AI classical baseline system.
> Intended for research reviewers, thesis examiners, and future quantum conversion.

---

## 1. Risk Classification Model

### 1.1 Single-Parameter Classification

For each hydrological variable v in { water_level_m, inflow_ktcmd, rainfall_mm_24h }:

```
risk_level(v) =
  CRITICAL    if v >= T_high
  HIGH        if T_moderate <= v < T_high
  MODERATE    if T_low <= v < T_moderate
  LOW         if v < T_low
```

**Threshold values (from `config/settings.py`):**

| Parameter | Low | Moderate | High (-> CRITICAL) |
|-----------|-----|----------|-------------------|
| water_level_m | 8.0 | 11.0 | 13.5 |
| inflow_ktcmd | 300.0 | 600.0 | 900.0 |
| rainfall_mm_24h | 30.0 | 70.0 | 120.0 |

### 1.2 Composite Risk (Worst-Case Rule)

```
overall_risk = max(risk_level(water_level), risk_level(inflow), risk_level(rainfall))
```

The composite rule takes the maximum (worst-case) severity across all three parameters. This is the conservative, documented rule used for disaster-response prioritisation.

---

## 2. Spatial Risk Attenuation Model

### 2.1 Exponential Decay (MODELLED_SPATIAL_ATTENUATION)

The forecast at the reference gauge (Prakasam Barrage) is spatially attenuated per zone:

```
f_z = exp(-d_z / lambda)
```

where:
- d_z = great-circle distance (km) from zone centroid to nearest point on river geometry
- lambda = 3.5 km (decay constant)

### 2.2 Effective Values

```
effective_water_level_z = base_water_level * f_z
effective_inflow_z      = base_inflow * f_z
effective_rainfall_z    = base_rainfall  (NOT attenuated -- uniform spatial distribution)
```

### 2.3 Proximity Bands

| Band | Distance | Factor |
|------|----------|--------|
| NEAR_RIVER | < 1.5 km | > 0.65 |
| MID_RANGE | 1.5 - 4.0 km | 0.32 - 0.65 |
| FAR_FROM_RIVER | > 4.0 km | < 0.32 |

**Note:** This is a modelled simplification, not measured per-zone water levels.

---

## 3. Sensor Placement Optimisation

### 3.1 Weighted Maximum Coverage Problem (NP-hard)

**Given:**
- N candidate sensor locations
- Z flood-risk zones with weights w_z
- Coverage radius R (km)
- Sensor budget K

**Decision variables:** x_j in {0, 1} for j in candidates

**Objective:**
```
max SUM(z in Z) w_z * c_z
```

where c_z = min(1, SUM(j: d(j,z) <= R) x_j) (zone covered if any sensor within radius).

**Subject to:** SUM(j) x_j <= K

### 3.2 Zone Weights

```
w_z = risk_score_z * 2.0   if risk_level_z == CRITICAL
w_z = risk_score_z          otherwise
```

### 3.3 Classical Solver: Greedy Set-Cover Approximation

At each step t = 1, ..., K:
1. For each remaining candidate j, compute marginal gain: delta_j = SUM(z in new(j)) w_z
2. Select j* = argmax(j) delta_j
3. Update covered set

**Optimality guarantee:** (1 - 1/e) ~ 63.2% of the optimal objective value (tight bound for Maximum Coverage).

### 3.4 Baseline Comparison: Naive Top-K

Individual score per candidate (ignoring overlap):
```
s_j = SUM(z: d(j,z) <= R) w_z
```

Select top-K by s_j. This typically underperforms the greedy approach when coverage areas overlap.

---

## 4. Communication Node Placement

### 4.1 Budgeted Maximum Sensor Connectivity

**Given:**
- Selected sensors S
- Communication range R_c (km)
- Communication node budget B

**Decision variables:** y_i in {0, 1} for i in S (co-locate comm node at sensor i)

**Objective:**
```
max SUM(s in S) connected(s)
```

where connected(s) = min(1, SUM(i: d(i,s) <= R_c) y_i)

**Subject to:** SUM(i) y_i <= B

**Solver:** Same greedy maximum-coverage algorithm, this time covering sensors instead of zones.

---

## 5. Adaptive Sensor Redeployment

### 5.1 Transition Optimisation

**Given:**
- Old deployment S_old, new optimal placement S_new

**Step 1:** Identify KEEP sites: S_old INTERSECT S_new

**Step 2:** Optimal bipartite matching (Hungarian algorithm) on unmatched sets:

```
min SUM((i,j) in M) d(s_i_old, s_j_new)
```

where M is a perfect matching on the smaller set. Uses `scipy.optimize.linear_sum_assignment` (Kuhn-Munkres, O(n^3)).

**Step 3:** Remaining unmatched new sites -> ADD; remaining old sites -> REMOVE.

---

## 6. Evacuation Routing

### 6.1 Risk-Penalised Shortest Path (Superlinear Risk Aversion)

**Given:** Road network graph G = (V, E) with edge distances d_e and modelled risk scores R_e.

**Edge cost function:**
```
c_e = d_e * (1 + beta * (R_e - 1)^1.5)
```

The superlinear exponent (1.5) makes CRITICAL-risk edges disproportionately expensive:

| Risk Level | Score R_e | Multiplier (beta=3.0) |
|------------|----------|-----------------------|
| LOW | 1 | 1.0 |
| MODERATE | 2 | 4.0 |
| HIGH | 3 | ~9.5 |
| CRITICAL | 4 | ~16.6 |

**Solver:** Dijkstra's algorithm with priority queue. Two routes computed:
1. **Primary:** Risk-averse (beta = 3.0)
2. **Alternative:** Shortest distance (beta = 0)

---

## 7. Emergency Resource Allocation

### 7.1 Multi-Resource Knapsack with Diminishing Returns

**Given:**
- Resources R = { rescue, medical, relief, vehicles } with budgets B_r and utility weights U_r
- Eligible zones Z with priority scores P_z
- Per-zone capacity caps M_zr

**Decision variables:** x_zr in {0, 1, ..., M_zr}

**Objective (Diminishing Marginal Utility):**
```
max SUM(z in Z) SUM(r in R) U_r * P_z * ln(1 + x_zr)
```

**Subject to:**
```
SUM(z in Z) x_zr <= B_r    for all r in R
x_zr <= M_zr               for all z, r
```

**Solver:** Marginal-utility greedy knapsack. At each step, allocate one unit to the (z, r) pair with the highest marginal gain:
```
delta_U = U_r * P_z * [ln(2 + x_zr) - ln(1 + x_zr)]
```

### 7.2 Zone Priority Score

```
P_z = 2 * risk_score_z + critical_boost(z) + max(0, 3 - d_z / 1.5)
```

where critical_boost = 3.0 for CRITICAL, 1.5 for HIGH, 0 otherwise.

---

## 8. Safe Location Evaluation (MCDA)

### 8.1 Multi-Criteria Decision Analysis

**Normalised factor scores** (0-1 scale):

```
norm_elev  = (elev - elev_min) / (elev_max - elev_min)
norm_risk  = 1 - (risk_score - 1) / 3
norm_dist  = (d_river - d_min) / (d_max - d_min)
norm_access = (a - a_min) / (a_max - a_min)
```

**Composite score:**
```
S = 100 * (w_elev * norm_elev + w_risk * norm_risk + w_dist * norm_dist + w_acc * norm_access)
```

**Default weights:** w_elev = 0.25, w_risk = 0.35, w_dist = 0.20, w_acc = 0.20.

---

## 9. Forecasting Model

### 9.1 Classical ML Pipeline

**Features:** Lag features (1, 2, 3, 7 days) for rainfall, inflow, water level; rolling means (3, 7 days) for rainfall and inflow; day_of_year, month.

**Target:** water_level_m[t + horizon] (shifted forward by horizon_days).

**Candidate models:** Linear Regression, Random Forest (200 trees, max_depth=8), Gradient Boosting (150 estimators, max_depth=3), Persistence Baseline.

**Selection:** Best model by lowest RMSE on chronological 80/20 train/test split (no shuffling).

**Leakage guard:** horizon_days >= 1 enforced; today's water_level_m[t] is a valid feature for predicting water_level_m[t+1] but would be leakage for same-day prediction.

---

## 10. Implemented Quantum Formulations

### 10.1 QUBO Formulation for Sensor Placement (Maximum Coverage with Budget K)

```
min H(x) = -Coverage(x) + P_budget * (SUM(j) x_j - K)^2 + lambda_parsimony * SUM(j) x_j
```

where:
- $x_j \in \{0, 1\}$ denotes selection of candidate sensor $j$.
- $P_{\text{budget}} > \max(\alpha_j)$ is an analytically safe penalty factor preventing budget violations.
- $\lambda_{\text{parsimony}} > 0$ is the minimal-nodes penalty that breaks ties in favor of smaller sensor counts for identical coverage.
- Exact Rosenberg reduction introduces auxiliary binary variables $u_z = x_{j0} x_{j1}$ for zones covered by 3 candidates:
  $-w_z x_{j0} x_{j1} x_{j2} \longrightarrow -w_z u_z x_{j2} + P_{\text{aux}} (x_{j0} x_{j1} - 2 x_{j0} u_z - 2 x_{j1} u_z + 3 u_z)$.

### 10.2 QAOA Statevector Simulation
The problem Hamiltonian $H_C$ is diagonal in the computational basis: $H_C |x\rangle = E(x) |x\rangle$.  
Evolved statevector:
$$|\psi(\gamma, \beta)\rangle = \prod_{l=1}^p \left[ e^{-i \beta_l \sum_j X_j} e^{-i \gamma_l H_C} \right] |+\rangle^{\otimes N}$$
Scipy COBYLA optimizes $(\gamma, \beta)$ to minimize $\langle\psi | H_C | \psi\rangle$.

### 10.3 Variational Quantum Regressor (VQR) for Hydrological Forecasting
- 4 qubits initialized to $|0000\rangle$.
- Data re-uploading with $R_y(\tilde{x})$ rotations for features: `water_level_m`, `inflow_ktcmd`, `rainfall_roll3`, `rainfall_mm`.
- Variational layers ($L=2$, 16 trainable parameters) with $R_z(\theta) R_x(\phi)$ gates and circular CNOT entanglement ring.
- Readout: $\langle Z_0 \rangle \in [-1, 1]$ scaled via affine mapping $\hat{y} = w \langle Z_0 \rangle + b$.
