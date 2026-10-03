"""
Rule-based Disaster Response Recommendation Engine.

Every recommendation below is generated from an explicit IF/THEN rule
evaluated against real pipeline outputs (forecast, risk zones, optimisation
result, connectivity result) - never a generic freeform AI paragraph.
"""


def generate_recommendations(risk_map: dict, opt_result, connectivity_result) -> dict:
    recommendations = []
    alerts = []

    base = risk_map["base_classification"]
    zones = risk_map["zones"]

    # Rule 1: overall system-level alert from base forecast classification
    if base["overall_risk"] in ("HIGH", "CRITICAL"):
        alerts.append({
            "level": base["overall_risk"],
            "message": f"Study-area forecast indicates {base['overall_risk']} flood risk. "
                       f"{base['explanation']}",
        })

    # Rule 2: uncovered CRITICAL/HIGH zones -> priority sensor deployment
    zone_lookup = {z["zone_id"]: z for z in zones}
    for zid in opt_result.uncovered_priority_zone_ids:
        z = zone_lookup.get(zid)
        if z and z["risk_level"] in ("CRITICAL", "HIGH"):
            recommendations.append({
                "priority": "HIGH" if z["risk_level"] == "CRITICAL" else "MEDIUM",
                "category": "SENSOR_DEPLOYMENT",
                "zone_id": zid,
                "message": f"Zone {zid} is classified {z['risk_level']} but currently has no "
                           f"sensor within coverage radius. Prioritise deployment of an "
                           f"additional monitoring sensor in this zone.",
            })

    # Rule 3: disconnected sensors -> communication support needed
    for sid in connectivity_result.disconnected_sensor_ids:
        recommendations.append({
            "priority": "MEDIUM",
            "category": "COMMUNICATION_SUPPORT",
            "sensor_id": sid,
            "message": f"Sensor {sid} is outside communication range of all deployed nodes. "
                       f"Recommend adding a relay communication node or extending range near this site.",
        })

    # Rule 4: critical zone coverage below threshold -> escalate
    if opt_result.critical_zone_coverage_percentage < 100 and any(z["risk_level"] == "CRITICAL" for z in zones):
        recommendations.append({
            "priority": "HIGH",
            "category": "COVERAGE_GAP",
            "message": f"Critical-zone coverage is at {opt_result.critical_zone_coverage_percentage}%. "
                       f"Increase sensor budget or re-run optimisation with an adjusted coverage radius "
                       f"to close remaining critical-zone gaps.",
        })

    # Rule 5: high overall coverage + full critical coverage -> stable state
    if opt_result.critical_zone_coverage_percentage == 100 and opt_result.coverage_percentage >= 70:
        recommendations.append({
            "priority": "LOW",
            "category": "STATUS",
            "message": "All critical zones are currently covered by deployed sensors with "
                       "strong overall coverage. Maintain current deployment and continue "
                       "routine monitoring.",
        })

    priority_areas = [
        {"zone_id": z["zone_id"], "risk_level": z["risk_level"], "centroid": z["centroid"]}
        for z in sorted(zones, key=lambda zz: zz["risk_score"], reverse=True)[:5]
    ]

    return {
        "alerts": alerts,
        "recommendations": recommendations,
        "priority_monitoring_areas": priority_areas,
    }
