"""
Reports API Routes
==================
Endpoints for generating and retrieving isolated disaster response reports.
Reports are rendered strictly from validated analysis bundles or explicit request payloads.
"""
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from app.services.analysis_store import analysis_store
from app.services.report_service import build_analysis_report, render_html_report

router = APIRouter()


class ReportGenerateRequest(BaseModel):
    analysis_id: Optional[str] = Field(default=None, description="Identifier of the analysis to report on")
    format: str = Field(default="json", description="Output format: 'json' or 'html'")
    bundle: Optional[Dict[str, Any]] = Field(default=None, description="Direct analysis payload if provided by caller")


@router.post("/reports/generate")
def generate_report(req: ReportGenerateRequest):
    """
    Generates a mutually consistent disaster response report for a specific analysis.
    Consumes either the stored analysis bundle by analysis_id or a direct payload.
    Never reads ambient process-global pipeline state.
    """
    bundle = req.bundle
    if not bundle and req.analysis_id:
        if not analysis_store.is_valid_id(req.analysis_id):
            raise HTTPException(status_code=400, detail="Invalid analysis ID format.")
        bundle = analysis_store.get(req.analysis_id)
        if not bundle:
            raise HTTPException(status_code=404, detail=f"Analysis '{req.analysis_id}' not found.")

    if not bundle:
        raise HTTPException(status_code=400, detail="Provide a valid 'analysis_id' or analysis 'bundle'.")

    report_data = build_analysis_report(bundle)

    if req.format.lower() == "html":
        html_content = render_html_report(report_data)
        return HTMLResponse(content=html_content, status_code=200)

    return report_data


@router.get("/reports/{analysis_id}")
def get_analysis_report(analysis_id: str, format: str = Query("json", description="'json' or 'html'")):
    """
    Retrieves the report for a specific analysis_id.
    Guards against path traversal and returns 404 if analysis does not exist.
    """
    if not analysis_store.is_valid_id(analysis_id):
        raise HTTPException(status_code=400, detail="Invalid analysis ID format.")

    bundle = analysis_store.get(analysis_id)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found.")

    report_data = build_analysis_report(bundle)

    if format.lower() == "html":
        html_content = render_html_report(report_data)
        return HTMLResponse(content=html_content, status_code=200)

    return report_data
