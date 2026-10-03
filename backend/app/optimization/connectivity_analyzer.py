"""
Communication Node & Connectivity Analysis
============================================
Two-stage approach (documented):

  Stage 1 (classical_optimizer.py): optimise sensor placement for weighted
  flood-risk coverage.

  Stage 2 (this module): place a LIMITED, BUDGETED set of communication
  nodes (`max_comm_nodes`) so that as many selected sensors as possible fall
  within `comm_range_km` of at least one communication node. UC-067 is
  explicit that both sensors AND communication nodes are limited resources -
  this module must never add unlimited nodes just to force full connectivity.

  Communication node candidate sites are the selected sensor locations
  themselves (i.e. any sensor site can also host a relay/communication
  unit - a standard simplification for constrained disaster-response
  networks where dedicated tower sites are not yet surveyed).

  We reuse the greedy maximum-coverage algorithm (this time covering
  SENSORS instead of ZONES) to choose communication node sites: at each
  step, pick the site that connects the most still-disconnected sensors,
  until either every sensor is connected, no site adds further connectivity,
  OR the `max_comm_nodes` budget is exhausted (whichever comes first). Any
  sensors left unconnected when the budget runs out are honestly reported
  as disconnected - not silently hidden.

All distances use the real haversine great-circle formula
(utils.geo_math.haversine_km) - no approximated/random logic.
"""
from dataclasses import dataclass
from app.utils.geo_math import haversine_km


@dataclass
class ConnectivityResult:
    comm_nodes: list
    connected_sensor_ids: list
    disconnected_sensor_ids: list
    connections: list  # [{sensor_id, comm_node_id, distance_km}]
    connectivity_percentage: float
    comm_range_km: float
    max_comm_nodes: int
    comm_nodes_used: int
    budget_exhausted: bool  # True if the node budget ran out before full connectivity


def analyze_connectivity(selected_sensors: list, comm_range_km: float, max_comm_nodes: int = None) -> ConnectivityResult:
    if not selected_sensors:
        return ConnectivityResult([], [], [], [], 0.0, comm_range_km, max_comm_nodes or 0, 0, False)

    # Precompute reachability: for each potential comm-node site (= a sensor
    # location), which sensors (including itself) fall within comm_range?
    reachability = {}
    for site in selected_sensors:
        reachable = set()
        for s in selected_sensors:
            d = haversine_km(site["lat"], site["lon"], s["lat"], s["lon"])
            if d <= comm_range_km:
                reachable.add(s["candidate_id"])
        reachability[site["candidate_id"]] = reachable

    all_sensor_ids = {s["candidate_id"] for s in selected_sensors}
    sensor_lookup = {s["candidate_id"]: s for s in selected_sensors}

    # Unbounded budget means "as many nodes as needed" (backward-compatible
    # default), but the caller should normally pass a real, limited budget.
    node_budget = max_comm_nodes if max_comm_nodes is not None else len(selected_sensors)

    comm_nodes = []
    connected = set()
    remaining_sites = dict(reachability)
    budget_exhausted = False

    while connected != all_sensor_ids and remaining_sites and len(comm_nodes) < node_budget:
        best_site, best_new = None, set()
        for site_id, reach in remaining_sites.items():
            new_covered = reach - connected
            if len(new_covered) > len(best_new):
                best_site, best_new = site_id, new_covered
        if best_site is None or not best_new:
            break
        comm_nodes.append({
            "comm_node_id": f"CN-{len(comm_nodes) + 1:02d}",
            "co_located_with": best_site,
            "lat": sensor_lookup[best_site]["lat"],
            "lon": sensor_lookup[best_site]["lon"],
            "connects_sensor_ids": sorted(best_new),
        })
        connected |= best_new
        del remaining_sites[best_site]

    if connected != all_sensor_ids and len(comm_nodes) >= node_budget:
        budget_exhausted = True

    disconnected = all_sensor_ids - connected

    connections = []
    for node in comm_nodes:
        for sid in node["connects_sensor_ids"]:
            s = sensor_lookup[sid]
            d = haversine_km(node["lat"], node["lon"], s["lat"], s["lon"])
            connections.append({
                "sensor_id": sid,
                "comm_node_id": node["comm_node_id"],
                "distance_km": round(d, 3),
            })

    connectivity_pct = (len(connected) / len(all_sensor_ids) * 100) if all_sensor_ids else 0.0

    return ConnectivityResult(
        comm_nodes=comm_nodes,
        connected_sensor_ids=sorted(connected),
        disconnected_sensor_ids=sorted(disconnected),
        connections=connections,
        connectivity_percentage=round(connectivity_pct, 2),
        comm_range_km=comm_range_km,
        max_comm_nodes=node_budget,
        comm_nodes_used=len(comm_nodes),
        budget_exhausted=budget_exhausted,
    )
