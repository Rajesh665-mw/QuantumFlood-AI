from fastapi import APIRouter
from app.gis.geo_loader import get_study_area_boundary, get_river_centerline, get_risk_zone_geometry
from app.config.settings import STUDY_AREA, MAP_CONFIG, get_max_bounds

router = APIRouter()


@router.get("/map/layers")
def get_map_layers():
    """
    Single source of truth for every map in the frontend: study area,
    base geometry layers, AND the map's display configuration (zoom limits,
    max bounds, tile provider) - so no page hardcodes its own zoom/bounds
    behaviour and every map page renders consistent geography.
    """
    return {
        "study_area": STUDY_AREA,
        "boundary": get_study_area_boundary(),
        "river": get_river_centerline(),
        "zones": get_risk_zone_geometry(),
        "geometry_mode": "MODELLED_SPATIAL",
        "map_config": MAP_CONFIG,
        "max_bounds": get_max_bounds(),
    }
