# search.py
import re
import time
from urllib.parse import urljoin
from browser import with_browser

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
    Extract listing URLs from a search results page.

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

        # Skip image gallery links
        if "/object/images/" in u:
            continue

        # Match new format: ends with -NUMBER.html (e.g., -3825677.html)
        if re.search(r"-\d+\.html$", u):
            urls.add(u)
        # Match old format: /object/NUMBER
        elif "/object/" in u:
            urls.add(u)

    return urls


def get_listing_urls(
    city: str, max_pages: int = 50, owner_only: bool = True
) -> list[str]:
    city = city.lower().strip()
    search_base = build_search_url(city, owner_only=owner_only)
    all_urls = set()

    def _goto_with_retry(page, url):
        """
        Navigate to url. If we land on the bot-detection page ("tuvastas võimaliku
        tórke"), wait 5s and retry once — kv.ee sometimes serves it as a one-time
        challenge before redirecting to the real page.
        Returns the body text after successful load.
        """
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")

        if "tuvastas võimaliku" in body.lower():
            # Wait for the redirect kv.ee promises, then retry
            print(f"  bot-detection page hit, waiting 5s and retrying...")
            page.wait_for_timeout(5000)
            # Sometimes kv.ee auto-redirects; if not, navigate again
            if "tuvastas võimaliku" in page.inner_text("body").lower():
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(3000)
            body = page.inner_text("body")

        return body

    def run(page):
        # Warm up: visit homepage first to get cookies/session tokens set.
        # kv.ee often blocks direct deep-links but allows navigation from homepage.
        print("warming up via homepage...")
        page.goto(f"{BASE}/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        for page_no in range(1, max_pages + 1):
            url = search_base + f"&page={page_no}"
            body = _goto_with_retry(page, url)

            if "Turvakontroll" in body:
                raise RuntimeError(
                    f"Captcha detected on page {page_no}. Body snippet: {body[:500]}"
                )

            if "tuvastas võimaliku" in body.lower():
                raise RuntimeError(
                    f"Bot detection page persisted after retry on page {page_no}. "
                    f"Body snippet: {body[:500]}"
                )

            batch = extract_listing_urls(page)
            new = batch - all_urls

            print(f"page {page_no}: +{len(new)} (total {len(all_urls) + len(new)})")

            # On page 1 with no results, log body for diagnosis
            if page_no == 1 and not new:
                raise RuntimeError(
                    f"Zero listing URLs found on page 1. "
                    f"Search URL: {url}\n"
                    f"Body snippet: {body[:1000]}"
                )

            if not new:
                break

            all_urls.update(batch)
            time.sleep(1)

        return sorted(all_urls)

    return with_browser(run)
