"""
Report Generation Service
=========================
Generates comprehensive, isolated audit and decision-support reports from an
explicitly identified analysis result bundle or request payload.

Never reads ambient process-global pipeline_state or shared latest_*.json files.
Produces consistent, traceable JSON and HTML reports with exact provenance metadata.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional


def build_analysis_report(analysis_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs a structured, comprehensive disaster-response report
    strictly from the provided analysis bundle.
    """
    analysis_id = analysis_bundle.get("analysis_id", "UNKNOWN")
    created_at = analysis_bundle.get("created_at", datetime.now(timezone.utc).isoformat())
    study_area = analysis_bundle.get("study_area", {})
    risk_map = analysis_bundle.get("risk_map")
    forecast = analysis_bundle.get("forecast")
    optimization = analysis_bundle.get("optimization")
    connectivity = analysis_bundle.get("connectivity")
    recommendations = analysis_bundle.get("recommendations")
    safe_locations = analysis_bundle.get("safe_locations")
    evacuation = analysis_bundle.get("evacuation_routes")
    resilience = analysis_bundle.get("resilience")
    resource_allocations = analysis_bundle.get("resource_allocations")
    scenario_params = analysis_bundle.get("scenario_params", {})

    # Study Area & Geographic Metadata
    bbox = study_area.get("bounding_box", {})
    center = study_area.get("center", {})
    is_default = study_area.get("is_default_location", False)
    river_feature = study_area.get("river_geojson")
    river_props = river_feature.get("properties", {}) if river_feature else {}

    provenance_summary = {
        "study_area_classification": "BENCHMARK_CORRIDOR" if is_default else "CUSTOM_MODELED_LOCATION",
        "river_waterway_source": river_props.get("data_source", "BENCHMARK_OSM" if is_default else "SIMULATED"),
        "is_synthetic_river": river_props.get("is_synthetic", not is_default),
        "hydrology_source": "SIMULATED_HYDROLOGY_TIME_SERIES",
    }

    # Summary Metrics
    summary = {
        "analysis_id": analysis_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "created_at": created_at,
        "location_name": study_area.get("name", "Unknown Area"),
        "center_coordinates": center,
        "bounding_box": bbox,
        "provenance": provenance_summary,
        "scenario_parameters": scenario_params,
    }

    sections = {}

    # Section 1: Flood Risk Assessment
    if risk_map:
        base_class = risk_map.get("base_classification", {})
        zones = risk_map.get("zones", [])
        critical_count = sum(1 for z in zones if z.get("risk_level") == "CRITICAL")
        high_count = sum(1 for z in zones if z.get("risk_level") == "HIGH")
        moderate_count = sum(1 for z in zones if z.get("risk_level") == "MODERATE")
        low_count = sum(1 for z in zones if z.get("risk_level") == "LOW")

        sections["risk_assessment"] = {
            "overall_system_risk": base_class.get("overall_risk", "UNKNOWN"),
            "risk_score": base_class.get("risk_score"),
            "driving_factor": base_class.get("driving_factor"),
            "explanation": base_class.get("explanation"),
            "total_zones_evaluated": len(zones),
            "zone_breakdown": {
                "critical": critical_count,
                "high": high_count,
                "moderate": moderate_count,
                "low": low_count,
            },
            "resolution": risk_map.get("resolution", "default"),
        }

    # Section 2: Sensor Placement Optimization
    if optimization:
        opt_data = optimization.get("optimization", optimization)
        sections["sensor_optimization"] = {
            "engine_type": opt_data.get("engine_type", "classical_greedy"),
            "sensors_requested": opt_data.get("num_sensors_requested"),
            "sensors_selected_count": opt_data.get("num_sensors_selected", len(opt_data.get("selected_sensors", []))),
            "coverage_percentage": opt_data.get("coverage_percentage"),
            "critical_zone_coverage_pct": opt_data.get("critical_zone_coverage_percentage"),
            "minimal_sensors_for_max_coverage": opt_data.get("minimal_sensors_for_max_coverage"),
            "selected_sensors": [
                {"id": s.get("candidate_id"), "lat": s.get("lat"), "lon": s.get("lon")}
                for s in opt_data.get("selected_sensors", [])
            ],
        }

    # Section 3: Telemetry & Network Connectivity
    if connectivity:
        sections["network_connectivity"] = {
            "connectivity_percentage": connectivity.get("connectivity_percentage"),
            "comm_nodes_used": connectivity.get("comm_nodes_used"),
            "comm_nodes_available": connectivity.get("max_comm_nodes"),
            "budget_exhausted": connectivity.get("budget_exhausted", False),
            "comm_nodes": [
                {"id": c.get("comm_node_id"), "lat": c.get("lat"), "lon": c.get("lon")}
                for c in connectivity.get("comm_nodes", [])
            ],
        }

    # Section 4: Evacuation & Safe Locations
    if safe_locations:
        locs = safe_locations.get("locations", safe_locations.get("safe_locations", []))
        sections["safe_locations"] = {
            "total_candidates": safe_locations.get("total_candidates", len(locs)),
            "recommended_count": len(locs),
            "top_locations": [
                {
                    "name": l.get("name"),
                    "elevation_m": l.get("elevation_m"),
                    "score": l.get("recommendation_score"),
                    "road_access": l.get("primary_road_access"),
                }
                for l in locs[:5]
            ],
        }

    if evacuation:
        sections["evacuation_routing"] = {
            "origin": evacuation.get("origin"),
            "destination": evacuation.get("destination"),
            "total_distance_km": evacuation.get("total_distance_km"),
            "risk_weighted_cost": evacuation.get("risk_weighted_cost"),
            "risk_exposure_level": evacuation.get("risk_exposure_level"),
            "safe_location_name": evacuation.get("safe_location_name"),
        }

    # Section 5: Recommendations
    if recommendations:
        sections["actionable_recommendations"] = recommendations.get("recommendations", recommendations)

    # Section 6: Forecasting
    if forecast:
        sections["hydrological_forecast"] = {
            "horizon_days": forecast.get("horizon_days"),
            "predicted_water_level_m": forecast.get("predicted_water_level_m"),
            "confidence_interval": forecast.get("confidence_interval"),
            "model_type": forecast.get("model_type", "classical"),
        }

    return {
        "analysis_id": analysis_id,
        "study_area": study_area,
        "summary": summary,
        "sections": sections,
    }



def render_html_report(report_data: Dict[str, Any]) -> str:
    """Renders the analysis report into a clean, standalone, semantic HTML document."""
    s = report_data.get("summary", {})
    sec = report_data.get("sections", {})
    risk = sec.get("risk_assessment", {})
    opt = sec.get("sensor_optimization", {})
    conn = sec.get("network_connectivity", {})
    safe = sec.get("safe_locations", {})
    evac = sec.get("evacuation_routing", {})
    recs = sec.get("actionable_recommendations", [])

    rec_list_html = "".join(
        f"<li><strong>[{r.get('priority', 'INFO')}]</strong> {r.get('message', '')}</li>"
        for r in (recs if isinstance(recs, list) else [])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>QuantumFlood AI Disaster Response Report — {s.get('analysis_id')}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; color: #1e293b; background: #f8fafc; line-height: 1.6; }}
    .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    h1 {{ color: #0f172a; margin-top: 0; }}
    h2 {{ color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 0; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
    .badge-critical {{ background: #fee2e2; color: #b91c1c; }}
    .badge-high {{ background: #ffedd5; color: #c2410c; }}
    .badge-moderate {{ background: #fef3c7; color: #b45309; }}
    .badge-low {{ background: #dcfce7; color: #15803d; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f1f5f9; }}
    .meta {{ font-size: 13px; color: #64748b; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>QuantumFlood AI — Situation &amp; Disaster Response Report</h1>
    <div class="meta">
      <strong>Analysis ID:</strong> {s.get('analysis_id')} &bull;
      <strong>Generated:</strong> {s.get('generated_at')} &bull;
      <strong>Location:</strong> {s.get('location_name')}
    </div>
  </div>

  <div class="card">
    <h2>1. Geographic Scope &amp; Provenance</h2>
    <p><strong>Center Coordinates:</strong> Lat {s.get('center_coordinates', {}).get('lat')}, Lon {s.get('center_coordinates', {}).get('lon')}</p>
    <p><strong>Provenance:</strong> {s.get('provenance', {}).get('study_area_classification')} ({s.get('provenance', {}).get('river_waterway_source')})</p>
  </div>

  {f'''<div class="card">
    <h2>2. Flood Risk Evaluation</h2>
    <p>Overall System Risk: <span class="badge badge-{risk.get('overall_system_risk', '').lower()}">{risk.get('overall_system_risk')}</span></p>
    <p>{risk.get('explanation', '')}</p>
    <table>
      <tr><th>Critical Zones</th><th>High-Risk Zones</th><th>Moderate Zones</th><th>Low Zones</th></tr>
      <tr>
        <td>{risk.get('zone_breakdown', {}).get('critical', 0)}</td>
        <td>{risk.get('zone_breakdown', {}).get('high', 0)}</td>
        <td>{risk.get('zone_breakdown', {}).get('moderate', 0)}</td>
        <td>{risk.get('zone_breakdown', {}).get('low', 0)}</td>
      </tr>
    </table>
  </div>''' if risk else ''}

  {f'''<div class="card">
    <h2>3. Sensor Deployment Optimization</h2>
    <p>Sensors Deployed: {opt.get('sensors_selected_count', 0)} &bull; Zone Coverage: {opt.get('coverage_percentage', 0)}% &bull; Critical Zone Coverage: {opt.get('critical_zone_coverage_pct', 0)}%</p>
    <p>Network Connectivity: {conn.get('connectivity_percentage', 'N/A')}% &bull; Communication Relays Used: {conn.get('comm_nodes_used', 'N/A')}</p>
  </div>''' if opt else ''}

  {f'''<div class="card">
    <h2>4. Actionable Response Recommendations</h2>
    <ul>{rec_list_html}</ul>
  </div>''' if rec_list_html else ''}
</body>
</html>"""
