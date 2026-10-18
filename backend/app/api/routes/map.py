from fastapi import APIRouter
from app.gis.geo_loader import get_study_area_boundary, get_river_centerline, get_risk_zone_geometry
from app.config.settings import STUDY_AREA, MAP_CONFIG, get_max_bounds
from app.services.active_area import is_default_area, get_active_area
from app.services.study_area_service import get_current_study_area

router = APIRouter()


@router.get("/map/layers")
def get_map_layers(lat: float = None, lon: float = None, half_size_deg: float = None, name: str = None):
    """
    Single source of truth for every map in the frontend: study area,
    base geometry layers, AND the map's display configuration (zoom limits,
    max bounds, tile provider).

    When latitude and longitude are supplied, resolves a request-scoped
    study area context without mutating the global active area.
    Otherwise falls back to current active or default study area.
    """
    if lat is not None and lon is not None:
        from app.services.study_area_service import resolve_study_area_context, _is_vijayawada_location
        study_area = resolve_study_area_context(latitude=lat, longitude=lon, half_size_deg=half_size_deg)
        is_default = _is_vijayawada_location(lat, lon)
    else:
        study_area = get_current_study_area()
        is_default = is_default_area()

    if is_default:
        map_config = MAP_CONFIG
        max_bounds = get_max_bounds()
    else:
        # Build dynamic map config from the study area
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
        "boundary": get_study_area_boundary(study_area=study_area),
        "river": get_river_centerline(study_area=study_area),
        "zones": get_risk_zone_geometry(study_area=study_area),
        "geometry_mode": "MODELLED_SPATIAL",
        "map_config": map_config,
        "max_bounds": max_bounds,
        "is_default_area": is_default,
    }
