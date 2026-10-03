"""
Central configuration for QuantumFlood AI (Classical Implementation).

All tunable constants live here so modules stay decoupled from
hardcoded magic numbers scattered through the codebase.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = APP_DIR / "data" / "raw"
DATA_GEO_DIR = APP_DIR / "data" / "geo"
DATA_PROCESSED_DIR = APP_DIR / "data" / "processed"
MODEL_DIR = DATA_PROCESSED_DIR / "models"
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_GEO_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Study area: Krishna river stretch near Vijayawada, Andhra Pradesh.
#
# HONEST SCOPE NOTE: this implementation covers ONE corridor within
# the much larger Krishna-Godavari basin, not the entire basin. All UI text
# must say so explicitly - see `scope_note` below, surfaced by the frontend.
#
# Reference coordinates below are REAL, sourced landmarks (not estimates):
#   - Prakasam Barrage: 16.50611N, 80.60500E - Wikipedia/Wikidata Q7238160,
#     citing the National Register of Large Dams 2019.
#   - Vijayawada city centroid: 16.5144N, 80.6192E - Wikipedia.
# ---------------------------------------------------------------------------
STUDY_AREA = {
    "name": "Vijayawada\u2013Krishna River Corridor",
    "region": "Krishna-Godavari Basin",
    "basin": "Krishna-Godavari Basin",
    "scope_note": (
        "Study area: the Vijayawada\u2013Krishna River corridor only "
        "\u2014 a single, well-defined corridor within the broader Krishna-Godavari basin. "
        "This implementation does not cover full basin-wide scope."
    ),
    "state": "Andhra Pradesh",
    "bounding_box": {
        "min_lat": 16.44,
        "max_lat": 16.56,
        "min_lon": 80.55,
        "max_lon": 80.72,
    },
    "center": {"lat": 16.50611, "lon": 80.60500},  # Prakasam Barrage (sourced, see above)
    "river": "Krishna River",
    "reference_gauge": "Prakasam Barrage",
    "reference_gauge_coords": {"lat": 16.50611, "lon": 80.60500},
    "reference_gauge_source": "Wikipedia / Wikidata Q7238160, citing National Register of Large Dams 2019",
}

# ---------------------------------------------------------------------------
# Map / GIS display configuration (single source of truth for every Leaflet
# map in the frontend - fetched via GET /api/map/layers so no page hardcodes
# its own zoom/bounds behaviour).
#
# - min_zoom / max_zoom: keep the user within a sensible viewing range for a
#   single river corridor (no world-scale zoom-out, no absurd zoom-in).
# - bounds_buffer_deg: geographic buffer added around the study bounding box
#   to form maxBounds, so panning stays anchored to the corridor with a bit
#   of surrounding context, but can't wander off to another continent.
# - tile provider: Standard OpenStreetMap raster tiles. Genuinely free, no
#   API key required, no registration, no paid dependency. Tile labels are
#   whatever OpenStreetMap's community dataset contains for this area.
#   Previous provider (CARTO Dark Matter) started returning "API KEY REQUIRED"
#   error tiles — replaced with the canonical OSM tile server.
# ---------------------------------------------------------------------------
MAP_CONFIG = {
    "min_zoom": 10,
    "max_zoom": 17,
    "default_zoom": 12,
    "bounds_buffer_deg": 0.12,
    "tile_url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "tile_subdomains": ["a", "b", "c"],
    "tile_attribution": (
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    ),
    "no_wrap": True,
    "world_copy_jump": False,
    "max_bounds_viscosity": 1.0,
}


def get_max_bounds() -> dict:
    """Returns Leaflet-ready max bounds (SW, NE corners) around the study
    bounding box, expanded by MAP_CONFIG['bounds_buffer_deg']. Used to stop
    the map panning/zooming away into a repeated/looping world view."""
    bbox = STUDY_AREA["bounding_box"]
    buf = MAP_CONFIG["bounds_buffer_deg"]
    return {
        "south_west": {"lat": bbox["min_lat"] - buf, "lon": bbox["min_lon"] - buf},
        "north_east": {"lat": bbox["max_lat"] + buf, "lon": bbox["max_lon"] + buf},
    }

# ---------------------------------------------------------------------------
# Risk thresholds (documented, rule-based - NOT random)
# Water level in metres above a nominal danger datum; inflow in cusecs-equivalent
# (thousand cubic metres/day, kTCM/day, for demo purposes).
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = {
    "water_level_m": {"low": 8.0, "moderate": 11.0, "high": 13.5},
    "inflow_ktcmd": {"low": 300.0, "moderate": 600.0, "high": 900.0},
    "rainfall_mm_24h": {"low": 30.0, "moderate": 70.0, "high": 120.0},
}

# ---------------------------------------------------------------------------
# Optimisation defaults
# ---------------------------------------------------------------------------
DEFAULT_NUM_SENSORS = 8
DEFAULT_COVERAGE_RADIUS_KM = 2.5
DEFAULT_COMM_RANGE_KM = 4.0
DEFAULT_MAX_COMM_NODES = 4  # limited communication-node budget (UC-067: LIMITED nodes)
DEFAULT_CRITICAL_WEIGHT_MULTIPLIER = 2.0  # extra weight given to CRITICAL zones

# Candidate generation: fraction of the distance from a zone centroid to the
# nearest point on the river geometry that a "near-river" candidate is moved
# toward the river (0 = stays at centroid, 1 = sits exactly on the river).
# Deterministic, geometry-driven - see optimization/candidate_generator.py.
CANDIDATE_RIVER_PULL_FRACTION = 0.55

# ---------------------------------------------------------------------------
# Simulated data generation seed (deterministic, documented — live CWC/KGBO
# telemetry feed is not yet integrated; all hydro time series are simulated)
# ---------------------------------------------------------------------------
DEMO_SEED = 42
DEMO_DAYS = 730  # two years of daily synthetic-but-deterministic records

# ---------------------------------------------------------------------------
# Risk-zone spatial resolution (Step 5): configurable grid granularity.
# "n" = number of grid divisions per side (n x n zones total).
# DEFAULT preserves the original behaviour (6x6 = 36 zones) so existing
# tests/behaviour are unaffected unless a resolution is explicitly requested.
# ---------------------------------------------------------------------------
RISK_ZONE_RESOLUTIONS = {
    "low": 4,       # 16 zones - coarser, fastest
    "default": 6,   # 36 zones - balanced (unchanged from earlier phases)
    "high": 10,     # 100 zones - finer analysis for experiments
}

# ---------------------------------------------------------------------------
# Data provenance registry: the single source of truth for which parts
# of the system use SIMULATED_INPUT, REAL_HISTORICAL, PARTIALLY_REAL,
# PROJECT_DEFINED, or MODELLED_SPATIAL data.
# The frontend's Data & Analytics / Data Provenance section reads this
# directly via GET /api/data/provenance — nothing is silently mixed.
# ---------------------------------------------------------------------------
DATA_PROVENANCE = {
    "rainfall_mm": {
        "status": "SIMULATED_INPUT",
        "reason": "Deterministic, seeded synthetic series. No live IMD/CWC rainfall feed integrated.",
    },
    "water_level_m": {
        "status": "SIMULATED_INPUT",
        "reason": "Deterministic, seeded synthetic series. No live CWC gauge feed integrated.",
    },
    "inflow_ktcmd": {
        "status": "SIMULATED_INPUT",
        "reason": "Deterministic, seeded synthetic series. No live CWC discharge feed integrated.",
    },
    "historical_flood_events": {
        "status": "REAL_HISTORICAL",
        "reason": "Documented flood events at Prakasam Barrage / Vijayawada, sourced from "
                   "published news and scientific reporting (see historical_flood_events_real.csv "
                   "metadata for per-record citations). Not a complete authoritative CWC record - "
                   "a small, citable sample of well-documented events.",
    },
    "river_geometry": {
        "status": "PARTIALLY_REAL",
        "reason": "Key waypoints (Prakasam Barrage, Bhavani Island, Kanaka Durga Varadhi, "
                   "Kanakadurga Flyover) are real, sourced landmark coordinates (Wikipedia/"
                   "Wikidata). Points between those anchors are interpolated, not surveyed. "
                   "A nationwide authoritative river-network GeoJSON exists at India's National "
                   "Water Data Portal (nwdp.nwic.gov.in) but exceeds a practical fetch size "
                   "(>30MB, whole-India) for this prototype; swapping it in later requires only "
                   "replacing krishna_river.geojson.",
    },
    "study_area_boundary": {
        "status": "PROJECT_DEFINED",
        "reason": "Rectangular scoping frame chosen by the project team, not an official "
                  "administrative or hydrological boundary polygon.",
    },
    "risk_zones": {
        "status": "MODELLED_SPATIAL",
        "reason": "Deterministic grid spatial model with exponential-decay spatial "
                  "attenuation: gauge-level forecast values are attenuated per zone by "
                  "exp(-distance/3.5km) for water level and inflow. Rainfall is applied "
                  "uniformly. Risk scoring logic is real, documented, rule-based "
                  "computation — not random assignment.",
    },
    "safe_candidate_locations": {
        "status": "PARTIALLY_REAL",
        "reason": "Facility names, coordinates, and road access match real civic/educational/medical complexes in the Vijayawada corridor. Elevations use SRTM 30m survey estimates. Live shelter status/capacity is not available from open telemetry and is explicitly marked UNAVAILABLE.",
    },
    "road_network": {
        "status": "PARTIALLY_REAL",
        "reason": "Network topology and edge lengths represent actual arterial roads and bridges in Vijayawada (NH-16, MG Road, Bandar Road, Eluru Road, Inner Ring Road, Barrage link, Kanaka Durga Varadhi). Real-time road inundation telemetry is not connected; route flood risks are modelled from zone risk classifications.",
    },
}

