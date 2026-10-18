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
    """Makes a rate-limited request to Nominatim with proper User-Agent and English language headers."""
    _rate_limit()
    # Enforce English language across all query endpoints
    params["accept-language"] = "en"
    query_string = urllib.parse.urlencode(params)
    url = f"{_NOMINATIM_BASE}/{endpoint}?{query_string}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept-Language": "en,en-US;q=0.9",
        },
    )
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
    Geocodes a location string (e.g. "Tokyo, Japan") into lat/lon + metadata with English labels.
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
        "namedetails": 1,
        "accept-language": "en",
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

    address = result.get("address") or {}
    namedetails = result.get("namedetails") or {}

    # Extract verified English name
    raw_name = (
        namedetails.get("name:en")
        or namedetails.get("int_name")
        or namedetails.get("name:latin")
        or result.get("name")
    )
    english_name = raw_name
    if english_name and any(ord(c) > 127 for c in str(english_name)):
        clean_q = query.split(",")[0].strip()
        if clean_q and all(ord(c) <= 127 for c in clean_q):
            english_name = clean_q
        else:
            # Transliterate or strip accents
            import unicodedata
            norm = unicodedata.normalize("NFKD", str(english_name)).encode("ascii", "ignore").decode("ascii").strip()
            english_name = norm if norm else clean_q

    city_val = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or ""
    )
    if any(ord(c) > 127 for c in str(city_val)) and english_name:
        city_val = english_name
    elif not city_val and english_name:
        city_val = english_name

    display_name_val = result.get("display_name", query)
    if any(ord(c) > 127 for c in str(display_name_val)):
        country_val = address.get("country", "")
        if english_name and country_val:
            display_name_val = f"{english_name}, {country_val}"
        elif english_name:
            display_name_val = english_name

    geocode_result = {
        "latitude": lat,
        "longitude": lon,
        "name": english_name or city_val or query,
        "name_en": english_name or city_val or query,
        "display_name": display_name_val,
        "place_type": result.get("type", "unknown"),
        "class": result.get("class", "unknown"),
        "importance": float(result.get("importance", 0.0)),
        "bounding_box": geo_bbox,
        "country": address.get("country", ""),
        "country_code": address.get("country_code", ""),
        "state": address.get("state", ""),
        "city": city_val,
    }

    # Cache result
    _geocode_cache[query_lower] = geocode_result
    return geocode_result


def reverse_geocode(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    """
    Reverse-geocodes a lat/lon into an English place name.
    """
    cache_key = f"rev_{lat:.5f}_{lon:.5f}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "addressdetails": 1,
        "namedetails": 1,
        "accept-language": "en",
    }

    data = _nominatim_request("reverse", params)
    if not data or "error" in data:
        return None

    address = data.get("address") or {}
    namedetails = data.get("namedetails") or {}

    english_name = (
        namedetails.get("name:en")
        or namedetails.get("int_name")
        or namedetails.get("name:latin")
        or data.get("name")
    )
    if english_name and any(ord(c) > 127 for c in str(english_name)):
        import unicodedata
        norm = unicodedata.normalize("NFKD", str(english_name)).encode("ascii", "ignore").decode("ascii").strip()
        english_name = norm if norm else (address.get("country") or f"{lat:.4f}, {lon:.4f}")

    city_val = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("state")
        or ""
    )
    if any(ord(c) > 127 for c in str(city_val)) and english_name:
        city_val = english_name
    elif not city_val and english_name:
        city_val = english_name

    display_name_val = data.get("display_name", f"{lat:.4f}, {lon:.4f}")
    if any(ord(c) > 127 for c in str(display_name_val)):
        country_val = address.get("country", "")
        if english_name and country_val:
            display_name_val = f"{english_name}, {country_val}"
        elif english_name:
            display_name_val = english_name

    result = {
        "name": english_name or city_val,
        "name_en": english_name or city_val,
        "display_name": display_name_val,
        "country": address.get("country", ""),
        "country_code": address.get("country_code", ""),
        "state": address.get("state", ""),
        "city": city_val,
    }

    _geocode_cache[cache_key] = result
    return result


def search_locations(query: str, limit: int = 5) -> list:
    """
    Searches for locations matching query, returning multiple candidates with English names.
    """
    query_clean = query.strip()
    if not query_clean:
        return []

    params = {
        "q": query_clean,
        "format": "json",
        "limit": min(limit, 10),
        "addressdetails": 1,
        "namedetails": 1,
        "accept-language": "en",
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
        addr = item.get("address") or {}
        namedetails = item.get("namedetails") or {}
        english_name = (
            namedetails.get("name:en")
            or namedetails.get("int_name")
            or namedetails.get("name:latin")
            or item.get("name")
        )
        if english_name and any(ord(c) > 127 for c in str(english_name)):
            import unicodedata
            norm = unicodedata.normalize("NFKD", str(english_name)).encode("ascii", "ignore").decode("ascii").strip()
            clean_q = query.split(",")[0].strip()
            english_name = norm if norm else clean_q

        city_val = (
            addr.get("city")
            or addr.get("town")
            or addr.get("village")
            or addr.get("municipality")
            or addr.get("state")
            or ""
        )
        if any(ord(c) > 127 for c in str(city_val)) and english_name:
            city_val = english_name
        elif not city_val and english_name:
            city_val = english_name

        disp_val = item.get("display_name", "")
        if any(ord(c) > 127 for c in str(disp_val)):
            country_val = addr.get("country", "")
            if english_name and country_val:
                disp_val = f"{english_name}, {country_val}"
            elif english_name:
                disp_val = english_name

        results.append({
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "name": english_name or city_val,
            "display_name": disp_val,
            "country": addr.get("country", ""),
            "city": city_val,
            "bounding_box": geo_bbox,
        })
    return results
