# main.py

from search import get_listing_urls
from listings import crawl_kv_listing
from db import init_db, save_listing
from analyze import analyze_all, fetch_listings_from_db, print_results


def main():
    init_db()

    area = input("Area (city or county, e.g. tallinn / harjumaa): ").strip().lower()
    urls = get_listing_urls(area)
    print(f"\nFound {len(urls)} listings\n")

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        data = crawl_kv_listing(url)
        save_listing(data)

    # Run LLM analysis on all listings
    print("\n" + "=" * 60)
    print("  ANALYZING LISTINGS WITH AI")
    print("=" * 60 + "\n")

    listings = fetch_listings_from_db()
    if listings:
        results = analyze_all(listings)
        print_results(results)
    else:
        print("No listings to analyze.")


if __name__ == "__main__":
    main()
