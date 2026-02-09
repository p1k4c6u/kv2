# main.py

from .search import get_listing_urls
from .listings import crawl_kv_listing
from .db import init_db, save_listing
from . import ui


def main():
    ui.show_banner()

    ui.show_info("Initializing database...")
    init_db()
    ui.show_success("Database ready")

    area = ui.prompt_area()
    ui.show_search_start(area)

    urls = get_listing_urls(area)
    ui.show_search_complete(len(urls))

    saved_count = 0
    for i, url in enumerate(urls, 1):
        data = crawl_kv_listing(url)
        save_listing(data)
        saved_count += 1

        ui.show_listing_result(
            index=i,
            total=len(urls),
            title=data.get("title"),
            price=data.get("price_eur"),
            url=url,
        )

    ui.show_crawl_complete(len(urls), saved_count)


if __name__ == "__main__":
    main()
