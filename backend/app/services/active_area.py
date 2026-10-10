"""
Active Study Area State
========================
Lightweight module-level singleton that holds the currently selected
study area configuration. Intentionally has NO imports from other app
modules to avoid circular dependencies — geo_loader, candidate_generator,
and risk_engine all import from here to check whether a dynamic area is
active before falling back to settings.STUDY_AREA.

The active area is set by POST /api/area/select and cleared on reset.
"""
import threading

_lock = threading.Lock()
_active_area: dict = None


def get_active_area() -> dict:
    """Returns the currently active study area config, or None if using default."""
    return _active_area


def set_active_area(area_config: dict) -> None:
    """Sets the active study area. Thread-safe."""
    global _active_area
    with _lock:
        _active_area = area_config


def clear_active_area() -> None:
    """Clears the active study area, reverting to default (Vijayawada)."""
    global _active_area
    with _lock:
        _active_area = None


def get_active_bounding_box() -> dict:
    """Returns the bounding box of the active area, or None."""
    area = _active_area
    if area is None:
        return None
    return area.get("bounding_box")


def get_active_center() -> dict:
    """Returns the center of the active area, or None."""
    area = _active_area
    if area is None:
        return None
    return area.get("center")


def get_active_river_geojson() -> dict:
    """Returns the river/water GeoJSON feature for the active area, or None."""
    area = _active_area
    if area is None:
        return None
    return area.get("river_geojson")


def is_default_area() -> bool:
    """Returns True if using the default (Vijayawada) study area."""
    return _active_area is None
