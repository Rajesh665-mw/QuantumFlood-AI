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

## 2. Platform Capabilities & Key Features

- **Core Navigation Modules (Five Primary Sections):**
  1. **Overview & Intelligence Home (`/`):** Executive flood risk posture, real-time gauge telemetry indicators, recent flood warnings, and workflow entrypoints.
  2. **Smart Sensor Placement (`/sensor-placement`):** Interactive map scanner, candidate generator, classical greedy vs. quantum QAOA optimizer, Pareto frontier minimal-node analysis, and RF line-of-sight connectivity telemetry.
  3. **Historical Flood Intelligence (`/historical-intelligence`):** Documented historical flood incidents at Prakasam Barrage (1903, 1998, 2009, 2024), peak discharge comparisons, zone inundation correlation, and strict data provenance transparency.
  4. **Safe Shelters & Logistics (`/safe-shelters`):** Multi-Criteria Decision Analysis (MCDA) ranking, verified operational relief centers vs. proposed candidate sites, risk-averse evacuation routing ($\beta = 3.0$), and shelter operator resource requests.
  5. **Resource Planning & Fulfillment (`/resource-planning`):** Central inventory dashboard, multi-resource knapsack allocation, algorithmic demand estimation, shelter supply approval & dispatch workflows, and immutable audit logs.
- **Multi-Model Hydrological Forecasting:** 1-day ahead water-level prediction evaluating Linear Regression, Random Forest, Gradient Boosting, a Persistence baseline, and an experimental 4-qubit Variational Quantum Regressor (VQR).
- **Rule-Based Spatial Flood Risk Mapping:** Deterministic risk scoring (LOW, MODERATE, HIGH, CRITICAL) mapped over configurable spatial grids with distance-to-river spatial attenuation.
- **RF Communication & Network Resilience:** Line-of-sight connectivity analysis between sensors and relay gateways with failure-node simulation.
- **Multi-Scenario Simulation:** Presets (Dry Season, Monsoon Normal, Extreme Inflow, Heavy Downpour) propagating updates across all downstream modules.

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
- **Testing:** Pytest (225 passing unit, domain invariant, integration, and audit tests).

### Repository Structure
```text
quantumflood-ai/
├── backend/                  # FastAPI REST API & Computational Engines
│   ├── app/
│   │   ├── api/routes/       # Modular API endpoints (forecast, optimization, etc.)
│   │   ├── config/           # Central settings & bounding coordinates
│   │   ├── data/             # Historical records, geojson, and benchmark datasets
│   │   ├── ml/               # Classical ML engines, pipelines, and evaluation
│   │   ├── optimization/     # Classical greedy approximation & QUBO builders
│   │   ├── quantum/          # Pure NumPy statevector QAOA & 4-qubit VQR engines
│   │   ├── schemas/          # Pydantic v2 domain schemas & validation models
│   │   ├── services/         # Business logic (shelter requests, routing, area)
│   │   └── tests/            # Automated test suite (225 tests)
│   └── requirements.txt      # Backend Python dependencies
├── frontend/                 # Vite + React 18 Single-Page Application
│   ├── src/
│   │   ├── components/       # Reusable UI cards, maps, legends, and toast system
│   │   ├── layouts/          # Responsive 5-section navigation layout
│   │   ├── pages/            # Primary workflow pages (Home, Sensors, Shelters, etc.)
│   │   ├── services/         # Typed API client with environment base URL resolution
│   │   └── utils/            # Shared chart themes and helper utilities
│   ├── package.json          # Frontend npm dependencies
│   ├── vercel.json           # Vercel SPA routing rewrite rules
│   └── vite.config.ts        # Vite dev server & proxy configuration
├── docs/                     # Architectural, mathematical, and empirical benchmark documentation
│   ├── mathematical_formulations.md
│   ├── QUANTUM_BENCHMARK_REPORT.md
│   └── QUANTUM_SYSTEM_ARCHITECTURE.md
├── .env.example              # Central environment configuration template
├── .gitignore                # Git ignore specifications
├── Dockerfile                # Container definition for containerized backend execution
├── LICENSE                   # MIT open source license
├── README.md                 # Primary system documentation and developer guide
├── render.yaml               # Render Blueprint for automated backend deployment
├── requirements.txt          # Root Python dependency pointer (-r backend/requirements.txt)
└── vercel.json               # Root Vercel deployment configuration
```

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
| **Linear Regression** | Classical ML | 0.0002 | 0.0003 | 1.0000 | Deterministic linear fit on lag features |
| **Gradient Boosting** | Classical ML | 0.0197 | 0.0350 | 0.9983 | Production tree ensemble |
| **Random Forest** | Classical ML | 0.0313 | 0.0510 | 0.9963 | Bagged ensemble baseline |
| **Persistence Baseline** | Classical Heuristic | 0.0531 | 0.0720 | 0.9926 | Naive "tomorrow = today" |
| **4-Qubit VQR (Persisted Artifact)** | Quantum ML (Sim) | 0.5773 | 0.6823 | 0.3406 | `qml_forecast_result.json` (Seed 42, `max_iter=15`) |
| **4-Qubit VQR (Exploratory Converged)** | Quantum ML (Sim) | 0.3540 | 0.4460 | 0.7182 | Dynamic API run (Seed 42, `max_iter=30`) |

**Multi-Seed Exploratory Evaluation (`evaluate_qml_multiseed`, `max_iter = 30`):**
- Seed 42: $R^2 = 0.7182$, MAE $0.3540\text{ m}$, RMSE $0.4460\text{ m}$
- Seed 123: $R^2 = 0.8239$, MAE $0.2656\text{ m}$, RMSE $0.3526\text{ m}$
- Seed 777: $R^2 = 0.6686$, MAE $0.4122\text{ m}$, RMSE $0.4837\text{ m}$
- Seed 2026: $R^2 = 0.8441$, MAE $0.2414\text{ m}$, RMSE $0.3318\text{ m}$
- **Summary:** Mean $R^2 = 0.7637 \pm 0.0728$, Mean MAE $0.3183\text{ m} \pm 0.0685\text{ m}$, Mean RMSE $0.4035\text{ m} \pm 0.0632\text{ m}$
- *Note:* The individual exploratory multi-seed runs are computed dynamically via API evaluation; `qml_forecast_result.json` remains the sole committed model artifact.

*Scientific Finding:* Verified classical models (Gradient Boosting and Linear Regression) outperform the 4-qubit simulated VQR on this continuous hydrological regression task.

### In-Depth Scientific & Architectural Documentation
For complete mathematical derivations, QUBO matrix formulations, and benchmark reproductions:
- **[Empirical Benchmark & Scientific Validation Report](docs/QUANTUM_BENCHMARK_REPORT.md):** 225-test verification matrix, 4-seed VQR evaluation, residual confidence interval calibration, and QAOA execution profiles.
- **[Hybrid System Architecture & Formulation Specification](docs/QUANTUM_SYSTEM_ARCHITECTURE.md):** Formal problem specifications for sensor placement, hydrological VQR, shelter site portfolios, and resource knapsack allocation.
- **[Mathematical Formulations Reference](docs/mathematical_formulations.md):** Detailed reference for exponential flood attenuation, distance-decay models, and classical optimality bounds.

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

See `.env.example` and `frontend/.env.example`.

---

## 10. Local Setup & Running

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Clone & Install
```bash
git clone https://github.com/Rajesh665-mw/QuantumFlood-AI.git
cd QuantumFlood-AI

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

---

## 11. Testing & Verification

Run the full pytest suite (225 tests):
```bash
cd backend
python -m pytest app/tests/ -v
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

#### Option 1: Blueprint Deployment via `render.yaml` (Recommended)
The repository includes a preconfigured [`render.yaml`](render.yaml) at root.
1. In the [Render Dashboard](https://dashboard.render.com), select **New > Blueprint**.
2. Connect your GitHub repository; Render will automatically detect `render.yaml` and configure the Python web service with start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

#### Option 2: Manual Web Service Setup
1. Create a new **Web Service** connected to your GitHub repository.
2. Configure settings:
   - **Root Directory:** `backend`
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Add Environment Variables:
   - `PYTHON_VERSION`: `3.11.9`
   - `FRONTEND_URL`: `https://your-app.vercel.app`
4. Deploy the service and copy the public URL to your frontend's `VITE_API_BASE_URL`.

---

## 13. License

This project is licensed under the [MIT License](LICENSE).
