"""
Location Service — Geocoding & Reverse Geocoding
==================================================
Uses the Nominatim geocoding API (OpenStreetMap) which is:
  - Free and open-source
  - No API key required
  - No billing or registration
  - Suitable for academic/research use

Usage policy: Nominatim requires a descriptive User-Agent header and
limits requests to 1 per second. This service respects those constraints
with rate limiting, caching, and error handling.

Reference: https://operations.osmfoundation.org/policies/nominatim/
"""
import time
import logging
import urllib.request
import urllib.parse
import urllib.error
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Nominatim usage policy: identify the application
_USER_AGENT = "QuantumFloodAI/2.0 (academic-research-project)"
_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"

# Simple in-memory cache to avoid repeat geocoding of the same query
_geocode_cache: Dict[str, Dict[str, Any]] = {}

# Rate limiting: track last request time
_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL: float = 1.1  # seconds (Nominatim policy: max 1 req/sec)


def _rate_limit():
    """Ensures at least _MIN_REQUEST_INTERVAL between Nominatim requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


def _nominatim_request(endpoint: str, params: dict) -> Optional[Any]:
    """Makes a rate-limited request to Nominatim with proper User-Agent."""
    _rate_limit()
    query_string = urllib.parse.urlencode(params)
    url = f"{_NOMINATIM_BASE}/{endpoint}?{query_string}"

    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning("Nominatim HTTP error %s: %s", e.code, e.reason)
        return None
    except urllib.error.URLError as e:
        logger.warning("Nominatim network error: %s", e.reason)
        return None
    except Exception as e:
        logger.warning("Nominatim unexpected error: %s", e)
        return None


def geocode(query: str) -> Optional[Dict[str, Any]]:
    """
    Geocodes a location string (e.g. "Tokyo, Japan") into lat/lon + metadata.

    Returns:
        {
            "latitude": float,
            "longitude": float,
            "display_name": str,
            "place_type": str,
            "importance": float,
            "bounding_box": {"min_lat": ..., "max_lat": ..., "min_lon": ..., "max_lon": ...},
            "country": str,
            "country_code": str,
        }
        or None if not found or error.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return None

    # Check cache
    if query_lower in _geocode_cache:
        logger.debug("Geocode cache hit for: %s", query)
        return _geocode_cache[query_lower]

    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "addressdetails": 1,
        "extratags": 1,
    }

    data = _nominatim_request("search", params)
    if not data or len(data) == 0:
        logger.info("Geocode: no results for '%s'", query)
        return None

    result = data[0]
    lat = float(result["lat"])
    lon = float(result["lon"])

    # Nominatim returns boundingbox as [min_lat, max_lat, min_lon, max_lon]
    bbox = result.get("boundingbox", [])
    if len(bbox) == 4:
        geo_bbox = {
            "min_lat": float(bbox[0]),
            "max_lat": float(bbox[1]),
            "min_lon": float(bbox[2]),
            "max_lon": float(bbox[3]),
        }
    else:
        geo_bbox = None

    address = result.get("address", {})

    geocode_result = {
        "latitude": lat,
        "longitude": lon,
        "display_name": result.get("display_name", query),
        "place_type": result.get("type", "unknown"),
        "class": result.get("class", "unknown"),
        "importance": float(result.get("importance", 0.0)),
        "bounding_box": geo_bbox,
        "country": address.get("country", ""),
        "country_code": address.get("country_code", ""),
        "state": address.get("state", ""),
        "city": address.get("city", address.get("town", address.get("village", ""))),
    }

    # Cache result
    _geocode_cache[query_lower] = geocode_result
    return geocode_result


def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Reverse-geocodes a lat/lon into a place name.
    Returns a dict with display_name, country, city, etc. or None.
    """
    cache_key = f"rev_{lat:.5f}_{lon:.5f}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
    }

    data = _nominatim_request("reverse", params)
    if not data or "error" in data:
        return None

    address = data.get("address", {})
    result = {
        "display_name": data.get("display_name", f"{lat}, {lon}"),
        "country": address.get("country", ""),
        "country_code": address.get("country_code", ""),
        "state": address.get("state", ""),
        "city": address.get("city", address.get("town", address.get("village", ""))),
    }

    _geocode_cache[cache_key] = result
    return result


def search_locations(query: str, limit: int = 5) -> list:
    """
    Searches for locations matching query, returning multiple candidates.
    Useful for interactive search and auto-complete in UI.
    """
    query_clean = query.strip()
    if not query_clean:
        return []

    params = {
        "q": query_clean,
        "format": "json",
        "limit": min(limit, 10),
        "addressdetails": 1,
    }

    data = _nominatim_request("search", params)
    if not data or not isinstance(data, list):
        return []

    results = []
    for item in data:
        bbox = item.get("boundingbox", [])
        geo_bbox = None
        if len(bbox) == 4:
            geo_bbox = {
                "min_lat": float(bbox[0]),
                "max_lat": float(bbox[1]),
                "min_lon": float(bbox[2]),
                "max_lon": float(bbox[3]),
            }
        addr = item.get("address", {})
        results.append({
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "display_name": item.get("display_name", ""),
            "country": addr.get("country", ""),
            "city": addr.get("city", addr.get("town", addr.get("village", ""))),
            "bounding_box": geo_bbox,
        })
    return results
