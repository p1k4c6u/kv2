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
    """
    Background task to run scraping.

    Uses a single browser session for the entire scrape so that the
    cf-clearance cookie (obtained once during search) persists across
    all listing page requests.
    """
    global _scrape_running, _last_scrape_result
    _scrape_running = True
    _last_scrape_result = None

    try:
        import os
        import time

        os.environ.setdefault("HEADLESS", "true")  # Force headless mode for API

        from db import init_db, save_listing
        from search import build_search_url, extract_listing_urls
        from listings import crawl_kv_listing, parse_listing, extract_listing_id
        from browser import with_browser, cf_goto

        init_db()

        def _run_in_browser(page):
            """Everything runs inside one browser session."""
            # --- Phase 1: collect listing URLs from search pages ---
            search_base = build_search_url(area, owner_only=True)
            all_urls = set()

            for page_no in range(1, 51):  # max 50 pages
                url = search_base + f"&page={page_no}"

                if page_no == 1:
                    cf_goto(page, url)  # solve CF once
                else:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    # Re-solve if cookie expired
                    title = page.evaluate("() => document.title")
                    if "just a moment" in title.lower():
                        cf_goto(page, url)

                batch = extract_listing_urls(page)
                new = batch - all_urls
                print(
                    f"search page {page_no}: +{len(new)} (total {len(all_urls) + len(new)})"
                )

                if not new:
                    if page_no == 1:
                        body = page.inner_text("body")
                        raise RuntimeError(
                            f"Zero listing URLs on page 1.\nBody: {body[:1000]}"
                        )
                    break

                all_urls.update(batch)
                time.sleep(1)

            urls = sorted(all_urls)
            print(f"Total URLs found: {len(urls)}")

            # --- Phase 2: scrape each listing (same session, CF cookie persists) ---
            saved = 0
            errors = []
            for i, listing_url in enumerate(urls):
                try:
                    data = crawl_kv_listing(listing_url, page=page)
                    save_listing(data)
                    saved += 1
                    print(f"  [{i + 1}/{len(urls)}] saved {data.get('listing_id')}")
                except Exception as e:
                    errors.append({"url": listing_url, "error": str(e)})
                    print(f"  [{i + 1}/{len(urls)}] error: {e}")
                    continue

                time.sleep(0.5)  # be polite

            return {"urls_found": len(urls), "saved": saved, "errors": errors[:10]}

        result = with_browser(_run_in_browser)

        _last_scrape_result = {
            "status": "complete",
            **result,
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
