"""
Dynamic Evacuation Routing Service
==================================
Calculates model-based evacuation routes across the Vijayawada–Krishna River
corridor using risk-penalised network graph traversal.

Mathematical Formulation (Quantum & Classical Graph Optimization):
  Graph G = (V, E) with edge distances d_e and modelled zone risk R_e.
  Decision variables: x_e in {0, 1} for e in E (1 if edge e is part of route).

  Objective (Risk-Penalised Shortest Path with Superlinear Risk Aversion):
    min sum_{e in E} [ d_e * (1 + beta * (R_e - 1)^1.5) ] * x_e

  The superlinear exponent (1.5) is intentional: it makes CRITICAL-risk edges
  disproportionately more expensive than HIGH-risk edges, reflecting the
  reality that evacuation routes through CRITICAL flood corridors are not
  just incrementally worse but qualitatively more dangerous. At beta=3.0:
    - LOW (R=1): multiplier = 1.0 (no penalty)
    - MODERATE (R=2): multiplier = 4.0
    - HIGH (R=3): multiplier = 1 + 3.0 * 2^1.5 ≈ 9.5
    - CRITICAL (R=4): multiplier = 1 + 3.0 * 3^1.5 ≈ 16.6

  Subject to flow conservation:
    sum_{v: (u,v) in E} x_uv - sum_{v: (v,u) in E} x_vu =
      1   if u = Origin (source)
     -1   if u = Destination (target)
      0   otherwise

  Classical solver: Dijkstra / Priority-queue shortest path with risk multipliers.
  Quantum-ready: Directly maps to QUBO / QAOA for constrained graph traversal.

Scientific Honesty Policy:
  - Clearly labelled as "Model-based evacuation route".
  - Does NOT assert live road closure or real-time barrier status.
"""
import heapq
import json
import logging
from typing import Optional, List, Dict, Any, Tuple

from app.config.settings import DATA_GEO_DIR
from app.utils.geo_math import haversine_km

logger = logging.getLogger(__name__)

_road_network_cache = None


def load_road_network() -> Dict[str, Any]:
    """Loads the corridor road network dataset from data/geo/road_network.json."""
    global _road_network_cache
    if _road_network_cache is None:
        path = DATA_GEO_DIR / "road_network.json"
        if not path.exists():
            return {"nodes": [], "edges": []}
        with open(path, "r", encoding="utf-8") as f:
            _road_network_cache = json.load(f)
    return _road_network_cache


def _build_adj_list(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
    adj = {n["id"]: [] for n in nodes}
    for e in edges:
        u, v = e["from"], e["to"]
        if u in adj and v in adj:
            adj[u].append((v, e))
            adj[v].append((u, e))  # Bidirectional road segments
    return adj


def _find_nearest_node(lat: float, lon: float, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    return min(nodes, key=lambda n: haversine_km(lat, lon, n["lat"], n["lon"]))


def _get_zone_risk_lookup(zones: List[Dict[str, Any]]) -> Dict[str, int]:
    return {z["zone_id"]: z.get("risk_score", 1) for z in zones}


def _get_edge_risk(edge: Dict[str, Any], nodes_lookup: Dict[str, Any], zones: List[Dict[str, Any]], zone_risk_map: Dict[str, int]) -> Tuple[int, str]:
    """Calculates risk level for an edge based on the zones traversed by its midpoint."""
    u_node = nodes_lookup.get(edge["from"])
    v_node = nodes_lookup.get(edge["to"])
    if not u_node or not v_node:
        return 1, "LOW"

    mid_lat = (u_node["lat"] + v_node["lat"]) / 2.0
    mid_lon = (u_node["lon"] + v_node["lon"]) / 2.0

    # Find zone
    assigned_zone = None
    for z in zones:
        b = z.get("bounds", {})
        if b.get("min_lat", 0) <= mid_lat <= b.get("max_lat", 0) and b.get("min_lon", 0) <= mid_lon <= b.get("max_lon", 0):
            assigned_zone = z
            break

    if not assigned_zone and zones:
        assigned_zone = min(
            zones,
            key=lambda z: haversine_km(mid_lat, mid_lon, z["centroid"]["lat"], z["centroid"]["lon"])
        )

    score = assigned_zone.get("risk_score", 1) if assigned_zone else 1
    level = assigned_zone.get("risk_level", "LOW") if assigned_zone else "LOW"

    # Riverfront road or river bridges carry intrinsic exposure multiplier during severe conditions
    if edge.get("road_class") in ("RIVERFRONT_ROAD", "RIVER_BRIDGE") and score > 1:
        score = min(score + 1, 4)
        level_map = {1: "LOW", 2: "MODERATE", 3: "HIGH", 4: "CRITICAL"}
        level = level_map[score]

    return score, level


def _dijkstra(
    start_id: str,
    target_id: str,
    adj: Dict[str, List[Tuple[str, Dict[str, Any]]]],
    nodes_lookup: Dict[str, Any],
    zones: List[Dict[str, Any]],
    zone_risk_map: Dict[str, int],
    risk_penalty_beta: float = 2.5
) -> Optional[Dict[str, Any]]:
    """Runs Dijkstra shortest path with risk penalty factor beta."""
    # pq entries: (cost, current_node, path_nodes, path_edges, total_km, total_risk_penalty)
    pq = [(0.0, start_id, [start_id], [], 0.0, 0.0)]
    visited = {}

    while pq:
        cost, curr, path, p_edges, dist_km, risk_pen = heapq.heappop(pq)

        if curr in visited and visited[curr] <= cost:
            continue
        visited[curr] = cost

        if curr == target_id:
            return {
                "nodes": path,
                "edges": p_edges,
                "distance_km": round(dist_km, 2),
                "risk_penalized_cost": round(cost, 2),
            }

        for neighbor, edge in adj.get(curr, []):
            edge_dist = edge["distance_km"]
            risk_score, _ = _get_edge_risk(edge, nodes_lookup, zones, zone_risk_map)

            penalty_mult = 1.0 + risk_penalty_beta * ((risk_score - 1) ** 1.5)
            edge_cost = edge_dist * penalty_mult

            new_cost = cost + edge_cost
            if neighbor not in visited or new_cost < visited.get(neighbor, float('inf')):
                heapq.heappush(
                    pq,
                    (new_cost, neighbor, path + [neighbor], p_edges + [edge], dist_km + edge_dist, risk_pen + edge_cost)
                )

    return None


def calculate_evacuation_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    zones: List[Dict[str, Any]],
    origin_name: str = "Origin Point",
    dest_name: str = "Destination Location",
    risk_penalty_beta: float = 3.0
) -> Dict[str, Any]:
    """
    Computes primary risk-averse evacuation route and alternative route.
    """
    network = load_road_network()
    nodes = network.get("nodes", [])
    edges = network.get("edges", [])

    if not nodes or not edges:
        return {
            "status": "ERROR",
            "message": "Corridor road network dataset is missing.",
            "primary_route": None,
            "alternative_route": None
        }

    nodes_lookup = {n["id"]: n for n in nodes}
    adj = _build_adj_list(nodes, edges)
    zone_risk_map = _get_zone_risk_lookup(zones)

    start_node = _find_nearest_node(origin_lat, origin_lon, nodes)
    dest_node = _find_nearest_node(dest_lat, dest_lon, nodes)

    # 1. Primary Risk-Averse Route (High Beta)
    primary_raw = _dijkstra(
        start_node["id"], dest_node["id"], adj, nodes_lookup, zones, zone_risk_map, risk_penalty_beta=risk_penalty_beta
    )

    # 2. Alternative Shortest Distance Route (Beta = 0)
    alt_raw = _dijkstra(
        start_node["id"], dest_node["id"], adj, nodes_lookup, zones, zone_risk_map, risk_penalty_beta=0.0
    )

    if not primary_raw:
        return {
            "status": "UNREACHABLE",
            "message": f"No accessible route between {origin_name} and {dest_name} on the road network.",
            "primary_route": None,
            "alternative_route": None
        }

    def _assemble_route(route_dict, is_primary: bool):
        edge_list = route_dict["edges"]
        node_ids = route_dict["nodes"]

        # Coordinates sequence
        coords = [[origin_lon, origin_lat]]
        for nid in node_ids:
            n = nodes_lookup[nid]
            coords.append([n["lon"], n["lat"]])
        coords.append([dest_lon, dest_lat])

        segments = []
        high_risk_count = 0
        total_risk_weight = 0.0

        for edge in edge_list:
            r_score, r_level = _get_edge_risk(edge, nodes_lookup, zones, zone_risk_map)
            u = nodes_lookup[edge["from"]]
            v = nodes_lookup[edge["to"]]

            is_high_risk = r_level in ("HIGH", "CRITICAL")
            if is_high_risk:
                high_risk_count += 1

            total_risk_weight += r_score * edge["distance_km"]

            segments.append({
                "edge_id": edge["id"],
                "road_name": edge["name"],
                "road_class": edge["road_class"],
                "distance_km": edge["distance_km"],
                "modelled_risk_score": r_score,
                "risk_level": r_level,
                "is_high_risk": is_high_risk,
                "start_coord": {"lat": u["lat"], "lon": u["lon"]},
                "end_coord": {"lat": v["lat"], "lon": v["lon"]},
                "warning": f"Traverses {r_level} modelled flood risk corridor" if is_high_risk else None
            })

        dist_km = route_dict["distance_km"]
        # Add access legs
        access_in = haversine_km(origin_lat, origin_lon, start_node["lat"], start_node["lon"])
        access_out = haversine_km(dest_node["lat"], dest_node["lon"], dest_lat, dest_lon)
        total_dist = round(dist_km + access_in + access_out, 2)

        weighted_avg_risk = round(total_risk_weight / dist_km, 2) if dist_km > 0 else 1.0

        return {
            "label": "Primary Risk-Averse Route" if is_primary else "Alternative Shortest Route",
            "total_distance_km": total_dist,
            "estimated_route_risk_score": weighted_avg_risk,
            "high_risk_segments_count": high_risk_count,
            "coordinates": coords,
            "segments": segments,
            "summary_nodes": [nodes_lookup[nid]["name"] for nid in node_ids],
            "start_node_name": start_node["name"],
            "dest_node_name": dest_node["name"]
        }

    primary_route = _assemble_route(primary_raw, is_primary=True)
    alt_route = _assemble_route(alt_raw, is_primary=False) if alt_raw else None

    # Route comparison & explanation
    if alt_route and alt_route["total_distance_km"] != primary_route["total_distance_km"]:
        risk_diff = round(alt_route["estimated_route_risk_score"] - primary_route["estimated_route_risk_score"], 2)
        dist_diff = round(primary_route["total_distance_km"] - alt_route["total_distance_km"], 2)

        if risk_diff > 0:
            explanation = (
                f"Primary Route avoids higher-risk inundation corridors, achieving an estimated route risk "
                f"score of {primary_route['estimated_route_risk_score']} vs {alt_route['estimated_route_risk_score']} "
                f"on the shortest path (+{dist_diff} km distance trade-off for significantly lower flood exposure)."
            )
        else:
            explanation = (
                f"Primary Route utilizes optimal corridor arteries with minimal flood exposure "
                f"(route risk score {primary_route['estimated_route_risk_score']})."
            )
    else:
        explanation = (
            f"The primary route via {start_node['name']} provides the lowest risk path to {dest_name} "
            f"with an average route risk score of {primary_route['estimated_route_risk_score']}."
        )

    return {
        "status": "SUCCESS",
        "origin": {"lat": origin_lat, "lon": origin_lon, "name": origin_name},
        "destination": {"lat": dest_lat, "lon": dest_lon, "name": dest_name},
        "primary_route": primary_route,
        "alternative_route": alt_route,
        "explanation": explanation,
        "data_provenance": {
            "road_network": "PARTIALLY_REAL",
            "edge_flood_risk": "MODELLED_SPATIAL",
            "closure_telemetry": "UNAVAILABLE"
        },
        "scientific_honesty_banner": (
            "Model-based evacuation route generated using modelled flood-risk data. "
            "Real-time road closure or inundation status is not available. Exercise caution."
        )
    }
