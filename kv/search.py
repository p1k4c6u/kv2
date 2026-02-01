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


def build_search_url(area: str) -> str:
    """
    Build kv.ee search URL for apartments (korterid) for sale in the given area.

    area can be:
      - city  (e.g. "tallinn") => county + parish filter
      - county (e.g. "harjumaa") => county filter only

    Owner-direct filtering is done client-side by checking for the
    "#Otse omanikult" tag on each listing card — not via URL params.
    """
    area = area.lower().strip()

    # city
    if area in CITY_TO_FILTERS:
        f = CITY_TO_FILTERS[area]
        return (
            f"{BASE}/kinnisvara/korterid?"
            f"act=search.simple&deal_type=1&county={f['county']}&parish={f['parish']}"
        )

    # county
    if area in COUNTY_TO_ID:
        county_id = COUNTY_TO_ID[area]
        return (
            f"{BASE}/kinnisvara/korterid?"
            f"act=search.simple&deal_type=1&county={county_id}"
        )

    raise ValueError(
        f"Unknown area '{area}'. Add it to CITY_TO_FILTERS or COUNTY_TO_ID."
    )


def extract_listing_urls(page) -> set[str]:
    """
    Extract listing URLs from a search results page.
    Returns only URLs (legacy interface, used by get_listing_urls).
    """
    return {url for url, _ in extract_listings_with_owner(page)}


def extract_listings_with_owner(page) -> list[tuple[str, bool]]:
    """
    Extract listing URLs + owner-direct flag from a search results page.

    Each listing on kv.ee is an <article> element. Owner-direct listings
    contain the text "Otse omanikult" somewhere inside the card.
    We read the listing URL from the article's data-object-url attribute
    (or fall back to the first matching <a> inside it).

    Returns list of (absolute_url, is_owner_direct) tuples.
    """
    js = """
    () => {
        const results = [];
        const articles = document.querySelectorAll('article[data-object-id]');

        for (const art of articles) {
            // Prefer data-object-url attribute (always present, clean)
            let href = art.getAttribute('data-object-url');
            if (!href) {
                // Fallback: first <a> with a listing-like href
                const a = art.querySelector('a[href$=".html"], a[href*="/object/"]');
                if (a) href = a.getAttribute('href');
            }
            if (!href) continue;

            const clean = href.split('?')[0];
            if (clean.includes('/object/images/')) continue;

            const text = art.innerText.toLowerCase();
            const isOwner = text.includes('otse omanikult');
            results.push({ href: clean, isOwner });
        }
        return results;
    }
    """
    raw = page.evaluate(js)

    listings = []
    for item in raw:
        url = urljoin(BASE, item["href"])
        listings.append((url, item["isOwner"]))

    return listings


PAGE_SIZE = 50  # kv.ee returns 50 listings per page


def paginated_url(search_base: str, page_no: int) -> str:
    """
    kv.ee pagination uses &start=N (offset), not &page=N.
    Page param is always 1; &start advances by PAGE_SIZE.

        page 1: ...&page=1
        page 2: ...&page=1&start=50
        page 3: ...&page=1&start=100
    """
    url = search_base + "&page=1"
    if page_no > 1:
        url += f"&start={(page_no - 1) * PAGE_SIZE}"
    return url


def get_listing_urls(city: str, max_pages: int = 50) -> list[str]:
    city = city.lower().strip()
    search_base = build_search_url(city)
    all_urls = set()

    def run(page):
        # First request will hit CF challenge. Solve it once, then the
        # cf-clearance cookie persists for the rest of the session.
        cf_goto(page, paginated_url(search_base, 1))

        for page_no in range(1, max_pages + 1):
            if page_no > 1:
                url = paginated_url(search_base, page_no)
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
                        f"Zero listing URLs on page 1.\nBody: {body[:1000]}"
                    )
                break

            all_urls.update(batch)
            time.sleep(1)

        return sorted(all_urls)

    return with_browser(run)
