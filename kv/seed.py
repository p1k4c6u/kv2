#!/usr/bin/env python3
"""
Local seed script — scrapes kv.ee with a VISIBLE browser so you can
manually solve the Cloudflare challenge once, then lets automation take over.

Usage:
    # Scrape and save to seed.json:
    python seed.py --area tallinn

    # Load a previously saved seed.json into a remote PostgreSQL DB:
    python seed.py --load seed.json --db postgresql://user:pass@host/db
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Make sure kv/ modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from browser import with_browser_visible, cf_goto
from search import build_search_url, extract_listing_urls
from listings import crawl_kv_listing


def scrape(area: str, output: str = "seed.json", max_pages: int = 50):
    """
    Scrape listing URLs + full listing data using a visible browser.
    The user must solve the CF challenge manually the first time.
    """
    search_base = build_search_url(area, owner_only=True)

    def run(page):
        # --- Phase 1: collect URLs ---
        all_urls = set()
        for page_no in range(1, max_pages + 1):
            url = search_base + f"&page={page_no}"

            if page_no == 1:
                print(f"Opening search page. If you see a Cloudflare challenge,")
                print(f"solve it manually in the browser, then press Enter here.")
                page.goto(url, wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(3000)

                title = page.evaluate("() => document.title")
                if "just a moment" in title.lower():
                    input(
                        "\n>>> Solve the CF challenge in the browser, then press Enter...\n"
                    )
                    # Wait for page to load after manual solve
                    page.wait_for_timeout(3000)
            else:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

                # If CF pops up again (unlikely after first solve in same session)
                title = page.evaluate("() => document.title")
                if "just a moment" in title.lower():
                    input("\n>>> CF challenge again. Solve it and press Enter...\n")
                    page.wait_for_timeout(3000)

            batch = extract_listing_urls(page)
            new = batch - all_urls
            print(
                f"  page {page_no}: +{len(new)} URLs (total {len(all_urls) + len(new)})"
            )

            if not new:
                if page_no == 1:
                    body = page.inner_text("body")
                    print(f"WARNING: Zero URLs on page 1. Body snippet:\n{body[:500]}")
                break

            all_urls.update(batch)
            time.sleep(1)

        urls = sorted(all_urls)
        print(f"\nTotal URLs: {len(urls)}")

        # --- Phase 2: scrape each listing ---
        listings = []
        for i, listing_url in enumerate(urls):
            try:
                data = crawl_kv_listing(listing_url, page=page)
                listings.append(data)
                owner = "OWNER" if data.get("is_owner_direct") else "agent"
                print(
                    f"  [{i + 1}/{len(urls)}] {data.get('listing_id'):>10} | {owner} | {data.get('title', 'no title')[:60]}"
                )
            except Exception as e:
                print(f"  [{i + 1}/{len(urls)}] ERROR: {e}")
                continue
            time.sleep(0.5)

        return listings

    listings = with_browser_visible(run)

    # Write output
    with open(output, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)

    owner_count = sum(1 for l in listings if l.get("is_owner_direct"))
    print(f"\nSaved {len(listings)} listings ({owner_count} owner-direct) to {output}")


def load(json_path: str, db_url: str):
    """
    Load seed JSON into a PostgreSQL database.
    """
    import os

    # Temporarily override DATABASE_URL so db.py picks it up
    os.environ["DATABASE_URL"] = db_url

    # Import after setting env so db.py doesn't blow up
    from db import init_db, save_listing

    with open(json_path, "r", encoding="utf-8") as f:
        listings = json.load(f)

    init_db()

    saved = 0
    errors = 0
    for l in listings:
        try:
            save_listing(l)
            saved += 1
        except Exception as e:
            print(f"  ERROR saving {l.get('listing_id')}: {e}")
            errors += 1

    owner_count = sum(1 for l in listings if l.get("is_owner_direct"))
    print(
        f"Loaded {saved} listings ({owner_count} owner-direct) into DB. Errors: {errors}"
    )


def main():
    parser = argparse.ArgumentParser(description="Seed kv.ee listing data")
    parser.add_argument(
        "--area", help="Area to scrape (tallinn, tartu, harjumaa, jõgevamaa)"
    )
    parser.add_argument(
        "--output", default="seed.json", help="Output JSON file (default: seed.json)"
    )
    parser.add_argument(
        "--max-pages", type=int, default=50, help="Max search result pages"
    )
    parser.add_argument("--load", metavar="FILE", help="Load a seed JSON file into DB")
    parser.add_argument("--db", help="PostgreSQL URL for --load mode")

    args = parser.parse_args()

    if args.load:
        if not args.db:
            print("ERROR: --db is required with --load")
            sys.exit(1)
        load(args.load, args.db)
    elif args.area:
        scrape(args.area, output=args.output, max_pages=args.max_pages)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
