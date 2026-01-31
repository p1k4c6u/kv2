# routes/scrape.py
"""
Scraping routes - trigger scraping for new listings.
"""

import sys
from pathlib import Path

# Add kv module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "kv"))

from fastapi import APIRouter, Depends, BackgroundTasks

from ..auth import verify_token
from ..schemas import ScrapeRequest, ScrapeResponse

router = APIRouter(prefix="/scrape", tags=["scrape"])

# Track running scrape jobs
_scrape_running = False
_last_scrape_result = None


def run_scrape(area: str):
    """Background task to run scraping."""
    global _scrape_running, _last_scrape_result
    _scrape_running = True
    _last_scrape_result = None

    try:
        # Import here to avoid circular imports and ensure env vars are loaded
        import os

        os.environ.setdefault("HEADLESS", "true")  # Force headless mode for API

        from db import init_db, save_listing
        from search import get_listing_urls
        from listings import crawl_kv_listing

        init_db()

        urls = get_listing_urls(area)

        for url in urls:
            try:
                data = crawl_kv_listing(url)
                save_listing(data)
            except Exception as e:
                print(f"Error scraping {url}: {e}")
                continue

        _last_scrape_result = {
            "status": "complete",
            "listings_found": len(urls),
        }
    except Exception as e:
        _last_scrape_result = {
            "status": "error",
            "error": str(e),
        }
    finally:
        _scrape_running = False


@router.post("", response_model=ScrapeResponse)
async def trigger_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    _: bool = Depends(verify_token),
):
    """
    Trigger scraping for a given area.
    Runs in the background using headless browser.

    Supported areas:
    - Cities: tallinn, tartu
    - Counties: harjumaa, jõgevamaa
    """
    global _scrape_running

    if _scrape_running:
        return ScrapeResponse(
            status="running",
            message="Scraping is already running. Please wait for it to complete.",
        )

    # Validate area
    valid_areas = ["tallinn", "tartu", "harjumaa", "jõgevamaa"]
    area = request.area.lower().strip()

    if area not in valid_areas:
        return ScrapeResponse(
            status="error",
            message=f"Invalid area '{area}'. Valid areas: {', '.join(valid_areas)}",
        )

    # Start background task
    background_tasks.add_task(run_scrape, area)

    return ScrapeResponse(
        status="started",
        message=f"Scraping started for {area}. This may take several minutes.",
    )


@router.get("/status")
async def get_scrape_status(
    _: bool = Depends(verify_token),
):
    """
    Check if scraping is currently running and get last result.
    """
    return {
        "running": _scrape_running,
        "last_result": _last_scrape_result,
    }
