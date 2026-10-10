from fastapi import APIRouter
from app.gis.geo_loader import get_study_area_boundary, get_river_centerline, get_risk_zone_geometry
from app.config.settings import STUDY_AREA, MAP_CONFIG, get_max_bounds
from app.services.active_area import is_default_area, get_active_area
from app.services.study_area_service import get_current_study_area

router = APIRouter()


@router.get("/map/layers")
def get_map_layers():
    """
    Single source of truth for every map in the frontend: study area,
    base geometry layers, AND the map's display configuration (zoom limits,
    max bounds, tile provider) - so no page hardcodes its own zoom/bounds
    behaviour and every map page renders consistent geography.

    When a dynamic study area is active, returns its configuration.
    Otherwise falls back to the default Vijayawada study area.
    """
    study_area = get_current_study_area()

    if is_default_area():
        map_config = MAP_CONFIG
        max_bounds = get_max_bounds()
    else:
        # Build dynamic map config from the active area
        from app.services.study_area_service import _build_map_config
        bbox = study_area.get("bounding_box", {})
        center = study_area.get("center", {})
        dynamic_config = _build_map_config(bbox, center)
        map_config = {
            "min_zoom": dynamic_config["min_zoom"],
            "max_zoom": dynamic_config["max_zoom"],
            "default_zoom": dynamic_config["default_zoom"],
            "bounds_buffer_deg": dynamic_config["bounds_buffer_deg"],
            "tile_url": dynamic_config["tile_url"],
            "tile_subdomains": dynamic_config["tile_subdomains"],
            "tile_attribution": dynamic_config["tile_attribution"],
            "no_wrap": dynamic_config["no_wrap"],
            "world_copy_jump": dynamic_config["world_copy_jump"],
            "max_bounds_viscosity": dynamic_config["max_bounds_viscosity"],
        }
        max_bounds = dynamic_config["max_bounds"]

    return {
        "study_area": study_area,
        "boundary": get_study_area_boundary(),
        "river": get_river_centerline(),
        "zones": get_risk_zone_geometry(),
        "geometry_mode": "MODELLED_SPATIAL",
        "map_config": map_config,
        "max_bounds": max_bounds,
        "is_default_area": is_default_area(),
    }
