"""
Aggregates optimisation + connectivity results into the coverage/analytics
figures shown on the Network & Coverage Analysis page. Pure computation over
already-produced results - no new randomness or fabrication.
"""


def build_coverage_summary(opt_result, connectivity_result, zones: list) -> dict:
    critical_zones = [z for z in zones if z["risk_level"] == "CRITICAL"]
    high_zones = [z for z in zones if z["risk_level"] == "HIGH"]

    critical_covered = [z["zone_id"] for z in critical_zones if z["zone_id"] in opt_result.covered_zone_ids]
    high_covered = [z["zone_id"] for z in high_zones if z["zone_id"] in opt_result.covered_zone_ids]

    return {
        "total_zones": len(zones),
        "total_coverage_percentage": opt_result.coverage_percentage,
        "high_risk_zone_total": len(high_zones),
        "high_risk_zone_covered": len(high_covered),
        "critical_zone_total": len(critical_zones),
        "critical_zone_covered": len(critical_covered),
        "critical_zone_coverage_percentage": opt_result.critical_zone_coverage_percentage,
        "sensor_budget": opt_result.num_sensors_requested,
        "sensors_deployed": opt_result.num_sensors_selected,
        "comm_node_budget": connectivity_result.max_comm_nodes,
        "comm_nodes_deployed": len(connectivity_result.comm_nodes),
        "comm_node_budget_exhausted": connectivity_result.budget_exhausted,
        "connected_sensors": len(connectivity_result.connected_sensor_ids),
        "disconnected_sensors": len(connectivity_result.disconnected_sensor_ids),
        "connectivity_percentage": connectivity_result.connectivity_percentage,
        "uncovered_priority_zone_ids": opt_result.uncovered_priority_zone_ids,
    }
