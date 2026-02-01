# search.py
import re
import time
from urllib.parse import urljoin
from browser import with_browser, cf_goto

BASE = "https://www.kv.ee"

CITY_TO_FILTERS = {
    "tallinn": {"county": 1, "parish": 421},
    "tartu": {"county": 7, "parish": 784},
}

COUNTY_TO_ID = {
    "harjumaa": 1,
    "jõgevamaa": 4,
}


def build_search_url(area: str, owner_only: bool = True) -> str:
    """
    area võib olla:
      - city (nt "tallinn") => county + parish
      - county (nt "harjumaa") => ainult county

    owner_only: lisab &bid_objects=1 => ainult "otse omanikult" tulemused
    """
    area = area.lower().strip()
    owner_param = "&bid_objects=1" if owner_only else ""

    # city
    if area in CITY_TO_FILTERS:
        f = CITY_TO_FILTERS[area]
        return (
            f"{BASE}/kinnisvara/korterid?"
            f"act=search.simple&deal_type=1&county={f['county']}&parish={f['parish']}{owner_param}"
        )

    # county
    if area in COUNTY_TO_ID:
        county_id = COUNTY_TO_ID[area]
        return (
            f"{BASE}/kinnisvara/korterid?"
            f"act=search.simple&deal_type=1&county={county_id}{owner_param}"
        )

    raise ValueError(
        f"Unknown area '{area}'. Add it to CITY_TO_FILTERS or COUNTY_TO_ID."
    )


def extract_listing_urls(page) -> set[str]:
    """
    Extract listing URLs from a search results page using Playwright.

    Handles both URL formats:
    - Old: /object/3825677
    - New: /something-something-3825677.html
    """
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )

    urls = set()
    for h in hrefs:
        if not h:
            continue
        if h.startswith("/"):
            u = urljoin(BASE, h.split("?")[0])
        else:
            continue

        if "/object/images/" in u:
            continue

        if re.search(r"-\d+\.html$", u):
            urls.add(u)
        elif "/object/" in u:
            urls.add(u)

    return urls


def get_listing_urls(
    city: str, max_pages: int = 50, owner_only: bool = True
) -> list[str]:
    city = city.lower().strip()
    search_base = build_search_url(city, owner_only=owner_only)
    all_urls = set()

    def run(page):
        # First request will hit CF challenge. Solve it once, then the
        # cf-clearance cookie persists for the rest of the session.
        first_url = search_base + "&page=1"
        cf_goto(page, first_url)

        for page_no in range(1, max_pages + 1):
            if page_no > 1:
                url = search_base + f"&page={page_no}"
                # After CF is solved, subsequent navigations should work directly
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # If we hit CF again (cookie expired), solve again
                title = page.evaluate("() => document.title")
                if "just a moment" in title.lower():
                    cf_goto(page, url)

            body = page.inner_text("body")

            if "Turvakontroll" in body:
                raise RuntimeError(f"Captcha on page {page_no}. Body: {body[:500]}")

            batch = extract_listing_urls(page)
            new = batch - all_urls

            print(f"page {page_no}: +{len(new)} (total {len(all_urls) + len(new)})")

            if not new:
                if page_no == 1:
                    raise RuntimeError(
                        f"Zero listing URLs on page 1. URL: {search_base}&page=1\n"
                        f"Body: {body[:1000]}"
                    )
                break

            all_urls.update(batch)
            time.sleep(1)

        return sorted(all_urls)

    return with_browser(run)
