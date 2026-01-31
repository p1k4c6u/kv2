# routes/analyze.py
"""
Analysis routes - trigger LLM analysis on listings.
"""

import sys
from pathlib import Path

# Add kv module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "kv"))

from fastapi import APIRouter, Depends, BackgroundTasks

from ..auth import verify_token
from ..schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter(prefix="/analyze", tags=["analyze"])

# Track running analysis jobs
_analysis_running = False


def run_analysis(limit: int | None = None):
    """Background task to run analysis."""
    global _analysis_running
    _analysis_running = True

    try:
        from analyze import fetch_listings_from_db, analyze_all

        listings = fetch_listings_from_db()
        if limit:
            listings = listings[:limit]

        analyze_all(listings, save_to_db=True, skip_analyzed=True)
    finally:
        _analysis_running = False


@router.post("", response_model=AnalyzeResponse)
async def trigger_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_token),
):
    """
    Trigger LLM analysis on unanalyzed listings.
    Runs in the background and saves results to database.
    """
    global _analysis_running

    if _analysis_running:
        return AnalyzeResponse(
            status="running",
            message="Analysis is already running. Please wait for it to complete.",
        )

    # Get counts for response
    from analyze import fetch_listings_from_db
    from db import get_analyzed_listing_ids

    listings = fetch_listings_from_db()
    analyzed_ids = get_analyzed_listing_ids()

    unanalyzed = [l for l in listings if l["listing_id"] not in analyzed_ids]

    if request.limit:
        unanalyzed = unanalyzed[: request.limit]

    if not unanalyzed:
        return AnalyzeResponse(
            status="complete",
            message="All listings have already been analyzed.",
            analyzed_count=0,
            skipped_count=len(listings),
        )

    # Start background task
    background_tasks.add_task(run_analysis, request.limit)

    return AnalyzeResponse(
        status="started",
        message=f"Analysis started for {len(unanalyzed)} listings. Check back later for results.",
        analyzed_count=len(unanalyzed),
        skipped_count=len(analyzed_ids),
    )


@router.get("/status")
async def get_analysis_status(
    _: bool = Depends(verify_token),
):
    """
    Check if analysis is currently running.
    """
    return {
        "running": _analysis_running,
    }
