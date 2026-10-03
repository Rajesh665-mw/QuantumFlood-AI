"""
Real historical flood event records for the Krishna River at Prakasam Barrage /
Vijayawada, sourced from published news and scientific reporting (NOT the
deterministic synthetic hydro series - that remains SIMULATED_INPUT).

Each record's discharge/date/severity claim traces to a specific cited source
in the `citation` column. This is a small, documented SAMPLE of well-reported
events, not a complete authoritative CWC flood archive. Discharge figures are
converted from the commonly reported unit (cusecs = cubic feet per second)
to SI (m^3/s) using 1 cusec = 0.0283168 m^3/s.

Run directly to (re)generate backend/app/data/raw/historical_flood_events_real.csv
"""
import pandas as pd
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))
from app.config.settings import DATA_RAW_DIR

CUSEC_TO_CUMEC = 0.0283168


def generate_real_flood_events() -> pd.DataFrame:
    events = [
        {
            "event_id": "EVT-1903",
            "year": 1903,
            "month": None,
            "location": "Prakasam Barrage site / Krishna River, Vijayawada",
            "peak_discharge_cusecs": None,
            "peak_discharge_cumecs": None,
            "severity_note": "Referenced as the prior record-holding flood before dams existed on the "
                              "river; the 2009 flood was reported as surpassing it.",
            "citation": "NASA Earth Observatory, 'Flooding Along the Krishna River' "
                        "(earthobservatory.nasa.gov/images/40601), citing PTI, 6 Oct 2009.",
        },
        {
            "event_id": "EVT-1998",
            "year": 1998,
            "month": "October",
            "location": "Nagarjuna Sagar Dam, upstream of Prakasam Barrage",
            "peak_discharge_cusecs": 800000,
            "peak_discharge_cumecs": round(800000 * CUSEC_TO_CUMEC, 1),
            "severity_note": "Previous highest recorded discharge at Nagarjuna Sagar (16 Oct 1998) "
                              "before being exceeded in 2009.",
            "citation": "Krishna River Floods Management report (SlideShare/ResearchGate mirror), "
                        "citing CWC discharge records.",
        },
        {
            "event_id": "EVT-2009",
            "year": 2009,
            "month": "October",
            "location": "Prakasam Barrage, Vijayawada",
            "peak_discharge_cusecs": 1143000,
            "peak_discharge_cumecs": round(1143000 * CUSEC_TO_CUMEC, 1),
            "severity_note": "Highest recorded discharge in the river's history at Prakasam Barrage "
                              "(11.43 lakh cusecs); water level rose to 21.9 ft against a full "
                              "reservoir level of 23 ft; ~276,000 people affected, ~250,000 evacuated.",
            "citation": "The South First (2 Sep 2024 retrospective); Deccan Herald "
                        "'Breaches in Krishna embankments flood more villages' (Oct 2009).",
        },
        {
            "event_id": "EVT-2024",
            "year": 2024,
            "month": None,
            "location": "Prakasam Barrage & Budameru rivulet, Vijayawada",
            "peak_discharge_cusecs": 1100000,
            "peak_discharge_cumecs": round(1100000 * CUSEC_TO_CUMEC, 1),
            "severity_note": "Prakasam Barrage released over 1.1 million cusecs; compounded by "
                              "Budameru rivulet overflow, submerging large parts of the city. "
                              "Described as one of the most devastating recent floods.",
            "citation": "IJRAR 'A Case Study on Recent Floods in Vijayawada' (ijrar.org/papers/IJRAR25A2756.pdf).",
        },
    ]
    df = pd.DataFrame(events)
    df["data_source"] = "REAL_HISTORICAL"
    return df


if __name__ == "__main__":
    df = generate_real_flood_events()
    out_path = DATA_RAW_DIR / "historical_flood_events_real.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
