# search.py
import re
import time
from urllib.parse import urljoin
from browser import with_browser

BASE = "https://www.kv.ee"

CITY_TO_FILTERS = {
    "tallinn": {"county": 1, "parish": 421},
    "tartu":   {"county": 7, "parish": 784},
}

COUNTY_TO_ID = {
    "harjumaa": 1,
    "jõgevamaa": 4,
}


def build_search_url(area: str) -> str:
    """
    area võib olla:
      - city (nt "tallinn") => county + parish
      - county (nt "harjumaa") => ainult county
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

    raise ValueError(f"Unknown area '{area}'. Add it to CITY_TO_FILTERS or COUNTY_TO_ID.")


def extract_listing_urls(page) -> set[str]:
    hrefs = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => e.getAttribute('href'))"
    )

    urls = set()
    for h in hrefs:
        if not h:
            continue
        if h.startswith("/"):
            u = urljoin(BASE, h.split("?")[0])
        else:
            continue

        if "/object/" in u or re.search(r"-\d+\.html$", u):
            urls.add(u)

    return urls

def get_listing_urls(city: str, max_pages: int = 50) -> list[str]:
    city = city.lower().strip()
    search_base = build_search_url(city)
    all_urls = set()

    def run(page):
        for page_no in range(1, max_pages + 1):
            url = search_base + f"&page={page_no}"
            page.goto(url, wait_until="domcontentloaded")

            body = page.inner_text("body")
            if "Turvakontroll" in body:
                input("Lahenda turvakontroll ja vajuta Enter...")

            batch = extract_listing_urls(page)
            new = batch - all_urls

            print(f"page {page_no}: +{len(new)} (total {len(all_urls)+len(new)})")

            if not new:
                break

            all_urls.update(batch)
            time.sleep(1)

        return sorted(all_urls)

    return with_browser(run)
