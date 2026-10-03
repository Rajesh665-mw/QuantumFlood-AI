r"""
Communication Failure & Network Resilience Service
==================================================
Simulates single or multi-node communication failures in the sensor telemetry
network, computes connectivity degradation, and algorithmically recommends
optimal recovery interventions.

Problem Formulation (Quantum-Ready Relay Placement Recovery):
  Given failed nodes F, surviving nodes N_surv = N \ F, and disconnected sensors S_disc.
  From candidate recovery relay sites C_relay:
  Decision variables:
    z_k in {0, 1} for k in C_relay (1 if recovery relay placed at site k)
    r_s in {0, 1} for s in S_disc (1 if disconnected sensor s is recovered)

  Objective (Maximum Connectivity Recovery):
    max sum_{s in S_disc} w_s * r_s - gamma * sum_{k in C_relay} cost(k) * z_k

  Constraints:
    r_s <= sum_{k: dist(k, s) <= R} z_k            (sensor recovery reachability)
    sum_{k} z_k <= B_rec                          (recovery relay budget)

  Classical Solver:
    Greedy maximum coverage across disconnected sensors with critical zone weighting.
"""
import logging
from typing import List, Dict, Any, Optional, Set

from app.utils.geo_math import haversine_km
from app.optimization.candidate_generator import generate_candidates

logger = logging.getLogger(__name__)


def simulate_network_failure(
    selected_sensors: List[Dict[str, Any]],
    comm_nodes: List[Dict[str, Any]],
    failed_node_ids: List[str],
    comm_range_km: float = 4.0,
    zones: Optional[List[Dict[str, Any]]] = None,
    candidate_pool: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Simulates node failures, determines isolated sensors and critical zone impacts,
    and computes the optimal recovery intervention.
    """
    if not selected_sensors:
        return {
            "status": "NO_SENSORS",
            "message": "No sensors deployed to analyze.",
            "metrics": {},
            "recovery_plan": None
        }

    sensor_lookup = {s["candidate_id"]: s for s in selected_sensors}
    all_sensor_ids = set(sensor_lookup.keys())
    failed_set = set(failed_node_ids)

    # 1. Baseline State (all comm nodes active)
    baseline_connected = set()
    baseline_connections = []
    for node in comm_nodes:
        n_lat, n_lon = node["lat"], node["lon"]
        for s in selected_sensors:
            sid = s["candidate_id"]
            d = haversine_km(n_lat, n_lon, s["lat"], s["lon"])
            if d <= comm_range_km:
                baseline_connected.add(sid)
                baseline_connections.append({
                    "sensor_id": sid,
                    "comm_node_id": node["comm_node_id"],
                    "distance_km": round(d, 2),
                    "status": "ACTIVE"
                })

    baseline_pct = (len(baseline_connected) / len(all_sensor_ids) * 100.0) if all_sensor_ids else 0.0

    # 2. Post-Failure State (remove failed nodes)
    surviving_nodes = [n for n in comm_nodes if n["comm_node_id"] not in failed_set]
    post_failure_connected = set()
    active_connections = []
    severed_connections = []

    for node in comm_nodes:
        n_lat, n_lon = node["lat"], node["lon"]
        is_failed = node["comm_node_id"] in failed_set
        for s in selected_sensors:
            sid = s["candidate_id"]
            d = haversine_km(n_lat, n_lon, s["lat"], s["lon"])
            if d <= comm_range_km:
                if not is_failed:
                    post_failure_connected.add(sid)
                    active_connections.append({
                        "sensor_id": sid,
                        "comm_node_id": node["comm_node_id"],
                        "distance_km": round(d, 2),
                        "status": "ONLINE"
                    })
                else:
                    severed_connections.append({
                        "sensor_id": sid,
                        "comm_node_id": node["comm_node_id"],
                        "distance_km": round(d, 2),
                        "status": "SEVERED"
                    })

    disconnected_sensor_ids = sorted(all_sensor_ids - post_failure_connected)
    failure_pct = (len(post_failure_connected) / len(all_sensor_ids) * 100.0) if all_sensor_ids else 0.0
    connectivity_loss_pct = round(baseline_pct - failure_pct, 2)

    # Critical zone impacts
    critical_zone_ids = set()
    if zones:
        critical_zone_ids = {z["zone_id"] for z in zones if z.get("risk_level") == "CRITICAL"}

    affected_critical_sensors = [
        sid for sid in disconnected_sensor_ids
        if sensor_lookup[sid].get("zone_id") in critical_zone_ids
    ]

    # 3. Algorithmic Recovery Recommendation
    # Determine candidate sites for a mobile/backup relay node
    candidates = candidate_pool
    if not candidates:
        candidates = generate_candidates()

    # Recovery algorithm: find candidate location that maximizes reconnection of disconnected sensors
    best_recovery_site = None
    best_reconnected: Set[str] = set()

    for cand in candidates:
        c_lat, c_lon = cand["lat"], cand["lon"]
        reconnected = set()
        for sid in disconnected_sensor_ids:
            s = sensor_lookup[sid]
            if haversine_km(c_lat, c_lon, s["lat"], s["lon"]) <= comm_range_km:
                reconnected.add(sid)

        # Prefer candidates that reconnect more sensors, prioritizing critical zones
        score = sum(2 if sensor_lookup[sid].get("zone_id") in critical_zone_ids else 1 for sid in reconnected)
        best_score = sum(2 if sensor_lookup[sid].get("zone_id") in critical_zone_ids else 1 for sid in best_reconnected)

        if score > best_score:
            best_recovery_site = cand
            best_reconnected = reconnected

    recovery_plan = None
    post_recovery_connected = set(post_failure_connected)

    if best_recovery_site and best_reconnected:
        post_recovery_connected |= best_reconnected
        recovery_pct = round(len(post_recovery_connected) / len(all_sensor_ids) * 100.0, 2)

        recovery_node = {
            "recovery_node_id": "REC-01",
            "candidate_id": best_recovery_site["candidate_id"],
            "lat": best_recovery_site["lat"],
            "lon": best_recovery_site["lon"],
            "reconnected_sensor_ids": sorted(best_reconnected),
            "reconnected_count": len(best_reconnected),
            "restored_connections": [
                {
                    "sensor_id": sid,
                    "recovery_node_id": "REC-01",
                    "distance_km": round(haversine_km(best_recovery_site["lat"], best_recovery_site["lon"], sensor_lookup[sid]["lat"], sensor_lookup[sid]["lon"]), 2),
                    "status": "RESTORED"
                }
                for sid in best_reconnected
            ]
        }

        recovery_explanation = (
            f"Deploy emergency backup communication node at candidate {best_recovery_site['candidate_id']} "
            f"({best_recovery_site.get('placement_method', 'STRATEGIC_SITE')}). "
            f"Algorithmically reconnects {len(best_reconnected)} isolated sensors ({', '.join(sorted(best_reconnected))}), "
            f"restoring network connectivity from {round(failure_pct, 1)}% back to {recovery_pct}%."
        )

        recovery_plan = {
            "action_type": "DEPLOY_BACKUP_RELAY",
            "recommended_site": recovery_node,
            "sensors_reconnected": sorted(best_reconnected),
            "reconnected_count": len(best_reconnected),
            "post_recovery_connectivity_pct": recovery_pct,
            "explanation": recovery_explanation
        }
    else:
        recovery_plan = {
            "action_type": "NO_VIABLE_RELAY_SITE",
            "recommended_site": None,
            "sensors_reconnected": [],
            "reconnected_count": 0,
            "post_recovery_connectivity_pct": round(failure_pct, 2),
            "explanation": "No candidate location within current comm range can bridge the disconnected sensors. Recommend increasing comm range or deploying multi-hop relay."
        }

    return {
        "status": "SUCCESS",
        "simulation_parameters": {
            "total_comm_nodes": len(comm_nodes),
            "failed_nodes_count": len(failed_set),
            "failed_node_ids": list(failed_set),
            "comm_range_km": comm_range_km
        },
        "metrics": {
            "total_sensors": len(all_sensor_ids),
            "baseline_connected": len(baseline_connected),
            "baseline_connectivity_pct": round(baseline_pct, 2),
            "post_failure_connected": len(post_failure_connected),
            "post_failure_disconnected": len(disconnected_sensor_ids),
            "post_failure_connectivity_pct": round(failure_pct, 2),
            "connectivity_loss_pct": connectivity_loss_pct,
            "affected_critical_sensors": affected_critical_sensors,
            "surviving_nodes_count": len(surviving_nodes),
        },
        "network_state": {
            "surviving_nodes": surviving_nodes,
            "failed_nodes": [n for n in comm_nodes if n["comm_node_id"] in failed_set],
            "active_connections": active_connections,
            "severed_connections": severed_connections,
            "disconnected_sensors": [sensor_lookup[sid] for sid in disconnected_sensor_ids]
        },
        "recovery_plan": recovery_plan
    }
