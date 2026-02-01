# search.py
import re
import time
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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


def extract_listing_urls_from_html(html: str) -> set[str]:
    """
    Extract listing URLs from search results page HTML using BeautifulSoup.

    Handles both URL formats:
    - Old: /object/3825677
    - New: /something-something-3825677.html
    """
    soup = BeautifulSoup(html, "html.parser")
    urls = set()

    for a in soup.find_all("a", href=True):
        h = a["href"]
        if not h.startswith("/"):
            continue

        u = urljoin(BASE, h.split("?")[0])

        # Skip image gallery links
        if "/object/images/" in u:
            continue

        # Match new format: ends with -NUMBER.html
        if re.search(r"-\d+\.html$", u):
            urls.add(u)
        # Match old format: /object/NUMBER
        elif "/object/" in u:
            urls.add(u)

    return urls


def get_listing_urls(
    city: str, max_pages: int = 50, owner_only: bool = True
) -> list[str]:
    """
    Fetch listing URLs from kv.ee search pages using cloudscraper
    to bypass Cloudflare bot detection. No browser needed for search.
    """
    city = city.lower().strip()
    search_base = build_search_url(city, owner_only=owner_only)
    all_urls = set()

    scraper = cloudscraper.create_scraper()

    for page_no in range(1, max_pages + 1):
        url = search_base + f"&page={page_no}"
        print(f"fetching page {page_no}: {url}")

        resp = scraper.get(url, timeout=30)

        if resp.status_code != 200:
            raise RuntimeError(
                f"HTTP {resp.status_code} on page {page_no}. "
                f"URL: {url}\n"
                f"Response snippet: {resp.text[:1000]}"
            )

        # Sanity check — if we still got a challenge page through
        if "just a moment" in resp.text.lower():
            raise RuntimeError(
                f"Cloudflare challenge page returned despite cloudscraper. "
                f"Page {page_no}, URL: {url}\n"
                f"HTML snippet: {resp.text[:2000]}"
            )

        batch = extract_listing_urls_from_html(resp.text)
        new = batch - all_urls

        print(f"page {page_no}: +{len(new)} (total {len(all_urls) + len(new)})")

        if not new:
            if page_no == 1:
                raise RuntimeError(
                    f"Zero listing URLs found on page 1. "
                    f"Search URL: {url}\n"
                    f"Body snippet: {resp.text[:1000]}"
                )
            break

        all_urls.update(batch)
        time.sleep(1)  # polite delay between pages

    return sorted(all_urls)
