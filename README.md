# QuantumFlood AI — Quantum-Enhanced Flood Forecasting and Disaster Response Optimization

**Flood Forecasting & Smart Sensor Placement for Disaster Response**  
*Problem Statement:* UC-067 · Krishna–Godavari Basin (Vijayawada–Krishna River Corridor) · Quantum Computing / Quantum AI-ML Track

> **Academic Architecture & Integrity Note:** QuantumFlood AI implements both verified classical production baselines and locally simulated quantum algorithms (QAOA sensor placement and 4-qubit Variational Quantum Regression with data re-uploading) executed via deterministic classical statevector simulation in pure NumPy. All experiments are reproducible, and classical models remain the verified production benchmark. Zero unproven quantum advantage or hardware supremacy is claimed.

---

## 1. Project Overview & Problem Statement

Flooding along the Krishna River basin—particularly at the bottleneck near the Prakasam Barrage in Vijayawada, Andhra Pradesh—poses severe risks to human life, critical infrastructure, and economic assets. Disaster mitigation requires two complementary capabilities:
1. **Accurate hydrologic forecasting:** Anticipating water-level surges hours or days in advance to enable proactive evacuation.
2. **Optimal sensory network design under constraints:** Maximizing sensor coverage over vulnerable zones while minimizing deployed equipment count and maintaining resilient RF communication backhauls.

**QuantumFlood AI** addresses Challenge UC-067 by integrating machine learning forecasting (classical ensembles and a simulated 4-qubit Variational Quantum Regressor) with combinatorial optimization solvers (classical greedy approximation and simulated QAOA on QUBO formulations). The system provides decision-support tools for zone-based spatial risk classification, sensor network placement, adaptive redeployment, evacuation routing, and emergency resource allocation.

---

## 2. Key Features

- **Multi-Model Hydrological Forecasting:** 1-day ahead water-level prediction evaluating Linear Regression, Random Forest, Gradient Boosting, a Persistence baseline, and an experimental 4-qubit Variational Quantum Regressor (VQR).
- **Rule-Based Spatial Flood Risk Mapping:** Deterministic risk scoring (LOW, MODERATE, HIGH, CRITICAL) mapped over configurable spatial grids (16, 36, or 100 zones) with distance-to-river spatial attenuation.
- **Minimal-Node Sensor Placement Optimization:**
  - *Classical Greedy Solver:* Maximum coverage heuristic with a provable $(1 - 1/e) \approx 63.2\%$ approximation ratio.
  - *Quantum QAOA Solver:* Quadratic Unconstrained Binary Optimization (QUBO) formulation solved via classical statevector simulation with exact Rosenberg polynomial reduction for multi-overlaps.
  - *Parsimonious Objective:* Diagonal penalty and Pareto frontier analysis determining the saturation point ($k^*$) where extra sensors yield diminishing coverage.
- **RF Communication & Network Resilience:** Haversine line-of-sight connectivity analysis between sensors and relay gateways, including failure-node simulation and graph connectivity tracking.
- **Downstream Disaster Response Support:**
  - *Safe Evacuation Centers:* Multi-Criteria Decision Analysis (MCDA) evaluating elevation, flood risk, distance to river, and road accessibility.
  - *Evacuation Routing:* Risk-penalized Dijkstra shortest path with superlinear risk aversion ($\beta = 3.0$) avoiding inundated zones.
  - *Adaptive Sensor Redeployment:* Bipartite minimum-cost matching (Hungarian algorithm) to reposition sensors with minimal transit distance.
  - *Emergency Resource Allocation:* Multi-resource knapsack with diminishing marginal returns ($\ln(1 + x)$) respecting capacity caps.
  - *Multi-Scenario Simulation:* Four presets (Dry Season, Monsoon Normal, Extreme Inflow, Heavy Downpour) propagating updates across all downstream modules.

---

## 3. System Architecture

```
                             [ Hydro-Met Inputs ]
                     (Rainfall, Inflow, Historical Events)
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │     ML & QML Forecasting Engine   │
                     │  - Classical: LinReg, RF, GBDT    │
                     │  - QML: 4-Qubit VQR (Simulated)   │
                     └─────────────────┬─────────────────┘
                                       │ Predicted Water Level
                                       ▼
                     ┌───────────────────────────────────┐
                     │     Spatial Risk Zone Engine      │
                     │  - Rule-based risk classification │
                     │  - Exponential spatial decay      │
                     └─────────────────┬─────────────────┘
                                       │ Risk Map & Vulnerabilities
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Sensor Placement Optimization   │
                     │  - Classical Greedy Approximation │
                     │  - QAOA QUBO Solver (Simulated)   │
                     │  - Pareto Frontier Minimal Nodes  │
                     └─────────────────┬─────────────────┘
                                       │ Deployed Sensors & Topology
                                       ▼
                     ┌───────────────────────────────────┐
                     │      RF Communication Network     │
                     │  - Relay connectivity analysis    │
                     │  - Node failure resilience        │
                     └─────────────────┬─────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌───────────────────┐         ┌───────────────────┐         ┌───────────────────┐
│  Safe Locations   │         │ Evacuation Router │         │ Resource Knapsack │
│  (MCDA Ranking)   │         │ (Dijkstra β=3.0)  │         │ (Diminishing Util)│
└───────────────────┘         └───────────────────┘         └───────────────────┘
```

---

## 4. Deployment Architecture

The application is structured into decoupled frontend and backend layers:

```
                      USER / BROWSER
                            │
                            ▼
               ┌──────────────────────────┐
               │      Vercel Frontend     │
               │   React 18 + Vite (SPA)  │
               └────────────┬─────────────┘
                            │
                            │ HTTPS REST Calls
                            │ (VITE_API_BASE_URL)
                            ▼
               ┌──────────────────────────┐
               │   FastAPI Backend API    │
               │ (Render / Railway / VM)  │
               └────────────┬─────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Classical ML    │ │ Simulated QAOA  │ │ 4-Qubit VQR     │
│ & Baselines     │ │ & QUBO Solvers  │ │ (NumPy Engine)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

- **Frontend on Vercel:** Static Vite SPA bundle with client-side routing fallback (`vercel.json`).
- **Backend on Dedicated Cloud/Container (Render, Railway, Fly.io, Cloud Run):** Hosts the computational runtime (FastAPI, NumPy, SciPy, Scikit-Learn, GeoPandas) with persistent state and dynamic CORS handling.

---

## 5. Technology Stack

- **Backend:** Python 3.10+, FastAPI 0.115, Uvicorn, Pydantic v2, NumPy 1.26, SciPy, Pandas, Scikit-Learn 1.5, Shapely, GeoPandas, Joblib, Pytest.
- **Frontend:** TypeScript 5.5, React 18.3, Vite 5.4, React Router 6, Tailwind CSS 3.4, Recharts, Leaflet / React-Leaflet, Lucide React.
- **Testing:** Pytest (136 unit, integration, and audit tests).

---

## 6. Quantum & Classical Implementations

### Quantum Components (Simulated)
- **QAOA for Sensor Placement:** Maps maximum coverage into a Quadratic Unconstrained Binary Optimization (QUBO) problem. Solved via a simulated QAOA ansatz with parameter optimization using classical statevector math in pure NumPy.
- **4-Qubit Variational Quantum Regressor (VQR):** Features parameterized $R_y(\theta)$ / $R_z(\theta)$ rotations, CNOT entangling layers, and data re-uploading across multiple circuit layers, trained with COBYLA.

### Classical Production Baselines
- **Forecasting Models:** Ordinary Least Squares (OLS) Linear Regression, Random Forest (200 trees), Gradient Boosting (150 estimators), and Persistence heuristic ("tomorrow = today").
- **Optimization:** Classical greedy maximum-coverage algorithm with submodular proof guarantees and exact brute-force search for small configurations ($N \le 12$).

### Canonical Forecasting Benchmark Results
Evaluated on 722 daily hydro-meteorological observations (80/20 chronological train/test split, 1-day forecast horizon):

| Model | Category | MAE (m) | RMSE (m) | R² Score | Note |
|---|---|---|---|---|---|
| **Linear Regression** | Classical ML | 0.0002 | 0.0003 | 1.0000 | Linear fit on lag features |
| **Gradient Boosting** | Classical ML | 0.0197 | 0.0350 | 0.9983 | Production tree ensemble |
| **Random Forest** | Classical ML | 0.0313 | 0.0510 | 0.9963 | Bagged ensemble baseline |
| **Persistence Baseline** | Classical Heuristic | 0.0531 | 0.0720 | 0.9926 | Naive "tomorrow = today" |
| **4-Qubit VQR (Seed 42)** | Quantum ML (Simulated) | 0.3540 | 0.4460 | 0.7182 | Local statevector simulation |
| **4-Qubit VQR (Seed 123)** | Quantum ML (Simulated) | 0.2656 | 0.3526 | 0.8239 | Local statevector simulation |
| **4-Qubit VQR (Seed 777)** | Quantum ML (Simulated) | 0.4122 | 0.4837 | 0.6686 | Local statevector simulation |
| **4-Qubit VQR (Seed 2026)** | Quantum ML (Simulated) | 0.2414 | 0.3318 | 0.8441 | Local statevector simulation |

**Multi-Seed Statistical Summary:**
- Mean $R^2$: $0.7637 \pm 0.0728$ (best: 0.8441, worst: 0.6686)
- Mean MAE: $0.3183\text{ m} \pm 0.0685\text{ m}$
- Mean RMSE: $0.4035\text{ m} \pm 0.0632\text{ m}$

*Scientific Finding:* Verified classical models (Gradient Boosting and Linear Regression) outperform the 4-qubit simulated VQR on this continuous hydrological regression task.

---

## 7. Data Provenance & Real vs. Simulated Inputs

The system enforces a strict data provenance contract surfaced at `/api/data/provenance` and displayed in the frontend:

| Data Category | Provenance Status | Description |
|---|---|---|
| **Rainfall Time Series** | `SIMULATED_INPUT` | Deterministic, seeded synthetic daily series (no live IMD telemetry). |
| **Water Level Time Series** | `SIMULATED_INPUT` | Deterministic, seeded synthetic daily series (no live CWC gauge telemetry). |
| **Inflow Time Series** | `SIMULATED_INPUT` | Deterministic, seeded synthetic daily series. |
| **Historical Flood Events** | `REAL_HISTORICAL` | Documented flood events at Prakasam Barrage (1903, 1998, 2009, 2024), cited from published news and technical reports. |
| **River Geometry** | `PARTIALLY_REAL` | Sourced landmark anchors (Prakasam Barrage, Bhavani Island, Kanaka Durga Varadhi, Kanakadurga Flyover) with interpolated centerline. |
| **Study Area Boundary** | `PROJECT_DEFINED` | Scoping rectangle for the Vijayawada corridor, not an official administrative boundary polygon. |
| **Spatial Risk Zones** | `MODELLED_SPATIAL` | Exponential-decay attenuation $\exp(-d/3.5\text{ km})$ from reference gauge to zone centroids. |
| **Road Network** | `PARTIALLY_REAL` | Real arterial road topology of Vijayawada (NH-16, MG Road, Bandar Road, etc.); inundation risk modelled from zone risk scores. |
| **Safe Evacuation Sites** | `PARTIALLY_REAL` | Real civic/educational facilities with SRTM 30m elevation estimates; live operational capacity marked unavailable. |

---

## 8. Current Assumptions & Limitations

1. **Hydrological Data:** Hydro-meteorological series are synthetic and deterministic to ensure reproducible evaluation in the absence of an open real-time government telemetry feed.
2. **Quantum Simulation:** QAOA and VQR circuits are executed using exact statevector simulation in NumPy on local classical hardware, not physical QPUs.
3. **Comparative Performance:** Classical ML models outperform the 4-qubit VQR on this dataset.
4. **RF Propagation:** Network connectivity uses great-circle line-of-sight distance without terrain elevation or canopy clutter modeling.
5. **Civic Recommendations:** Evacuation routing and resource allocations are academic decision-support prototypes, not certified civil defense instructions.

---

## 9. Environment Variables

| Variable | Target | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Frontend | `""` (uses `/api` proxy) | URL of the deployed FastAPI backend (e.g., `https://quantumflood-api.onrender.com`). |
| `PORT` | Backend | `8000` | Port on which the FastAPI Uvicorn server binds. |
| `HOST` | Backend | `0.0.0.0` | Host IP address on which Uvicorn binds. |
| `FRONTEND_URL` | Backend | `""` | Comma-separated URLs of deployed frontends to permit via CORS. |
| `ALLOWED_ORIGINS` | Backend | `""` | Additional explicit CORS origins. |
| `ALLOWED_ORIGIN_REGEX` | Backend | `^https:\/\/.*\.vercel\.app$` | Regex allowing all Vercel preview/production domains. |
| `ALLOW_ALL_ORIGINS` | Backend | `false` | Set to `true` only for completely open demo instances. |

See `.env.example`, `frontend/.env.example`, and `backend/.env.example`.

---

## 10. Local Setup & Running

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Clone & Install
```bash
git clone https://github.com/your-username/quantumflood-ai.git
cd quantumflood-ai

# Install backend dependencies
cd backend
python -m pip install -r requirements.txt
cd ..

# Install frontend dependencies
cd frontend
npm install
cd ..
```

### 2. Run Backend
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at: `http://localhost:8000/docs`

### 3. Run Frontend
```bash
cd frontend
npm run dev
```
Interactive Dashboard will be available at: `http://localhost:5173`

*(On Windows, you can also use `install.bat`, `start-backend.bat`, `start-frontend.bat`, or `start-all.bat`.)*

---

## 11. Testing & Verification

Run the full pytest suite (136 tests):
```bash
cd backend
python -m pytest -v
```
Build the frontend for production:
```bash
cd frontend
npm run build
```

---

## 12. Deployment Guide

### A. Deploying the Frontend to Vercel

1. Push your repository to GitHub.
2. In your [Vercel Dashboard](https://vercel.com/new), click **Import Project** and select your repository.
3. Configure the project settings:
   - **Framework Preset:** Vite
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
   - **Install Command:** `npm install`
4. Set Environment Variables in Vercel:
   - `VITE_API_BASE_URL`: The HTTPS URL of your deployed backend (e.g., `https://your-backend.onrender.com`).
5. Click **Deploy**.
   *Note: `frontend/vercel.json` automatically configures SPA rewrite rules so direct page refreshes work.*

### B. Deploying the Backend API (Render, Railway, Fly.io, or Cloud Run)

The backend requires a persistent Python 3.10+ container runtime with C-library support for GeoPandas and NumPy.

#### Example: Deploying on [Render.com](https://render.com)
1. Create a new **Web Service** connected to your GitHub repository.
2. Configure settings:
   - **Root Directory:** `backend`
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add Environment Variables:
   - `PYTHON_VERSION`: `3.10.12` (or 3.11/3.12)
   - `FRONTEND_URL`: `https://your-app.vercel.app`
4. Deploy the service and copy the public URL to your frontend's `VITE_API_BASE_URL`.

---

## 13. License

This project is licensed under the [MIT License](LICENSE).
