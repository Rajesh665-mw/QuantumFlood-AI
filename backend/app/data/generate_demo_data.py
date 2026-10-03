"""
DEMO / SIMULATION MODE DATA GENERATOR
======================================
Generates a deterministic, documented, seeded synthetic dataset that stands
in for a live CWC / KGBO telemetry feed for the Krishna river at the
Vijayawada study area, until a real data source is connected.

This is NOT random noise dressed up as data:
- The seasonal (monsoon) shape is a deterministic sinusoidal + trend model.
- A fixed numpy seed (settings.DEMO_SEED) makes every run reproducible.
- Values are clearly documented and bounded to physically plausible ranges
  for the Krishna basin (e.g. dry-season baseflow vs monsoon peak).
- This file is the ONLY place synthetic values are produced. Replacing it
  with a real CWC/IMD data loader requires no changes anywhere else in the
  pipeline, because downstream modules only consume the resulting CSV
  schema (date, rainfall_mm, water_level_m, inflow_ktcmd).

Run directly to (re)generate backend/app/data/raw/krishna_hydro_demo.csv
"""
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.config.settings import DATA_RAW_DIR, DEMO_SEED, DEMO_DAYS


def generate_hydro_meteorological_series(days: int = DEMO_DAYS, seed: int = DEMO_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)  # fixed seed -> fully reproducible
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    day_of_year = np.array([d.timetuple().tm_yday for d in dates])

    # --- Rainfall: monsoon-shaped seasonal curve (peak ~ day 200, Jul-Sep) ---
    monsoon_phase = 2 * np.pi * (day_of_year - 200) / 365.0
    seasonal_rain = 45 * np.clip(np.cos(monsoon_phase), 0, 1) ** 2
    # Deterministic bounded perturbation (not unbounded randomness): a small
    # reproducible day-to-day variability layered on the seasonal curve.
    daily_variability = 8 * rng.standard_normal(days)
    rainfall_mm = np.clip(seasonal_rain + daily_variability, 0, None)

    # --- Inflow: responds to rainfall with a short lag + baseflow ---
    baseflow = 180.0
    inflow = np.zeros(days)
    for i in range(days):
        lag_rain = rainfall_mm[max(0, i - 1)] * 0.6 + rainfall_mm[max(0, i - 2)] * 0.3
        seasonal_component = 250 * np.clip(np.cos(monsoon_phase[i]), 0, 1) ** 2
        inflow[i] = baseflow + seasonal_component + lag_rain * 5.5
    inflow_ktcmd = np.clip(inflow, 100, None)

    # --- Water level: responds to inflow via a smoothed relationship ---
    water_level = 6.0 + 0.0065 * inflow_ktcmd
    # 3-day rolling smoothing to mimic reservoir/river routing lag
    water_level = pd.Series(water_level).rolling(3, min_periods=1).mean().to_numpy()

    df = pd.DataFrame({
        "date": [d.strftime("%Y-%m-%d") for d in dates],
        "rainfall_mm": np.round(rainfall_mm, 2),
        "inflow_ktcmd": np.round(inflow_ktcmd, 2),
        "water_level_m": np.round(water_level, 3),
    })
    df["data_source"] = "SIMULATED_INPUT"
    return df


def generate_historical_flood_events() -> pd.DataFrame:
    """Deterministic, documented sample of historical flood events used for
    threshold calibration context (illustrative demo record, not official
    CWC archive data)."""
    events = [
        {"event_id": "EVT-2009", "year": 2009, "month": "October", "severity": "CRITICAL",
         "peak_water_level_m": 15.2, "location": "Vijayawada / Prakasam Barrage"},
        {"event_id": "EVT-2020", "year": 2020, "month": "August", "severity": "HIGH",
         "peak_water_level_m": 13.1, "location": "Vijayawada / Prakasam Barrage"},
        {"event_id": "EVT-2022", "year": 2022, "month": "July", "severity": "MODERATE",
         "peak_water_level_m": 11.4, "location": "Krishna delta upstream stretch"},
    ]
    df = pd.DataFrame(events)
    df["data_source"] = "SIMULATED_INPUT"
    return df


if __name__ == "__main__":
    hydro_df = generate_hydro_meteorological_series()
    hydro_path = DATA_RAW_DIR / "krishna_hydro_demo.csv"
    hydro_df.to_csv(hydro_path, index=False)
    print(f"Wrote {len(hydro_df)} rows to {hydro_path}")

    flood_df = generate_historical_flood_events()
    flood_path = DATA_RAW_DIR / "historical_flood_events_demo.csv"
    flood_df.to_csv(flood_path, index=False)
    print(f"Wrote {len(flood_df)} rows to {flood_path}")
