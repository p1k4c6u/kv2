# listings.py

import re
from bs4 import BeautifulSoup
from browser import with_browser, cf_goto


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def extract_listing_id(url: str) -> str:
    m = re.search(r"/object/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"-(\d+)\.html$", url)
    if m:
        return m.group(1)
    return url


def extract_description_text(soup: BeautifulSoup) -> str:
    node = soup.select_one(
        ".object-text, .object-description, .description, #description"
    )
    if node:
        return node.get_text("\n", strip=True)
    return (soup.body or soup).get_text("\n", strip=True)


def find_first(patterns: list[str], text: str):
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            return normalize_spaces(m.group(1))
    return None


def parse_listing(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    full_text = normalize_spaces(soup.get_text(" "))

    data = {}

    # title
    h1 = soup.find("h1")
    data["title"] = normalize_spaces(h1.get_text(" ")) if h1 else None

    # price + eur/m2 (KV lehel tavaliselt koos)
    # proovime mitu varianti, sest mõnel lehel on teistmoodi
    price = find_first(
        [
            r"(\d[\d\s\u00A0]*)\s*€",  # "1 150 000 €"
        ],
        full_text,
    )
    if price:
        data["price_eur"] = int(re.sub(r"[^\d]", "", price))

    eur_m2 = find_first(
        [
            r"(\d[\d\s\u00A0]*)\s*€/m²",
            r"(\d[\d\s\u00A0]*)\s*€/m2",
        ],
        full_text,
    )
    if eur_m2:
        data["eur_per_m2"] = int(re.sub(r"[^\d]", "", eur_m2))

    # “label → value” tüüpi väljad (mitme mustriga)
    # NB: need jäävad tihti samasse teksti kujule: "Tube 4", "Üldpind 233.6 m²", jne.
    def grab(label: str):
        return find_first(
            [
                rf"{re.escape(label)}\s*[:\-]?\s*([0-9A-Za-zÕÄÖÜõäöü\.,]+(?:\s*m²|\s*m2|\s*km|\s*ha|\s*aasta|\s*korrus|\s*€)?)",
                rf"{re.escape(label)}\s+([0-9A-Za-zÕÄÖÜõäöü\.,]+(?:\s*m²|\s*m2)?)",
            ],
            full_text,
        )

    data["rooms"] = grab("Tube")
    data["bedrooms"] = grab("Magamistube")
    data["total_area"] = grab("Üldpind")
    data["floors"] = grab("Korruseid")
    data["year_built"] = grab("Ehitusaasta")
    data["condition"] = grab("Seisukord")
    data["ownership"] = grab("Omandivorm")
    data["plot_area"] = grab("Krundi pind")
    data["cadastral_nr"] = grab("Katastrinumber")
    data["energy_class"] = grab("Energiamärgis")

    # description + lisainfo
    desc = extract_description_text(soup)
    data["description"] = desc if desc else None

    m = re.search(r"(?im)^\s*Lisainfo\s*:\s*(.+?)\s*$", desc or "")
    if m:
        raw = m.group(1).strip()
        data["additional_info_raw"] = raw
        data["additional_info"] = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        data["additional_info_raw"] = None
        data["additional_info"] = []

    # Owner vs realtor detection — kv.ee marks direct-owner listings with "otse omanikult"
    full_text_lower = full_text.lower()
    data["is_owner_direct"] = "otse omanikult" in full_text_lower

    # Grab seller/contact block raw text for reference
    seller_node = soup.select_one(
        ".seller-info, .contact-info, .object-seller, .agent-info, "
        "[class*='seller'], [class*='contact'], [class*='agent']"
    )
    data["seller_info"] = (
        normalize_spaces(seller_node.get_text(" ")) if seller_node else None
    )

    return data


def crawl_kv_listing(url: str, page=None) -> dict:
    """
    Scrape a single listing page.

    Args:
        url: The listing URL on kv.ee
        page: An existing Playwright page (shared browser session with cf-clearance).
              If None, opens a new browser — useful for one-off scraping.
    """

    def _scrape(p):
        cf_goto(p, url)

        body = p.inner_text("body")
        if "Turvakontroll" in body:
            raise RuntimeError(f"Captcha on listing page {url}. Body: {body[:500]}")

        html = p.content()
        data = parse_listing(html)
        data["url"] = url
        data["listing_id"] = extract_listing_id(url)
        return data

    if page is not None:
        # Shared session — cf-clearance cookie already set, cf_goto will
        # skip the challenge automatically.
        return _scrape(page)
    else:
        # Standalone — opens its own browser, will need to solve CF fresh.
        return with_browser(_scrape)
