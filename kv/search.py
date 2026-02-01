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


def _is_listing_href(h: str) -> bool:
    """Check if an href looks like a kv.ee listing URL."""
    if not h or not h.startswith("/"):
        return False
    if "/object/images/" in h:
        return False
    clean = h.split("?")[0]
    return bool(re.search(r"-\d+\.html$", clean) or "/object/" in clean)


def extract_listing_urls(page) -> set[str]:
    """
    Extract listing URLs from a search results page.
    Returns only URLs (legacy interface, used by get_listing_urls).
    """
    return {url for url, _ in extract_listings_with_owner(page)}


def extract_listings_with_owner(page) -> list[tuple[str, bool]]:
    """
    Extract listing URLs + owner-direct flag from a search results page.

    kv.ee marks owner-direct listings with a "#Otse omanikult" tag inside
    each listing card on the search results page. We walk each card's DOM
    to associate the tag with its listing URL.

    Returns list of (absolute_url, is_owner_direct) tuples.
    """
    # Run JS in-page: for every <a> that looks like a listing link,
    # walk up to find the nearest listing card ancestor, then check if
    # that card contains the "otse omanikult" text anywhere.
    # kv.ee listing cards are typically .object-card, .list-item, or
    # similar containers. We use a generic approach: find the closest
    # ancestor that is a direct child of the results list, or fall back
    # to checking the whole page text if no clear card boundary exists.
    js = """
    () => {
        const results = [];
        const anchors = document.querySelectorAll('a[href]');
        const seen = new Set();

        for (const a of anchors) {
            const href = a.getAttribute('href');
            if (!href || !href.startsWith('/')) continue;
            const clean = href.split('?')[0];
            // Match listing hrefs: /object/12345 or /something-12345.html
            if (!/(-\\d+\\.html$|\\/object\\/\\d)/.test(clean)) continue;
            if (clean.includes('/object/images/')) continue;
            if (seen.has(clean)) continue;
            seen.add(clean);

            // Walk up to find the listing card container.
            // Try known card classes first, then fall back to a generic
            // "large enough ancestor" heuristic.
            let card = null;
            let el = a;
            for (let i = 0; i < 10; i++) {
                el = el.parentElement;
                if (!el) break;
                const cls = (el.className || '').toLowerCase();
                if (cls.includes('object') || cls.includes('card') ||
                    cls.includes('list-item') || cls.includes('listing')) {
                    card = el;
                    break;
                }
            }
            // Fallback: use the <a> itself (narrow scope but safe)
            if (!card) card = a;

            const text = card.innerText.toLowerCase();
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
