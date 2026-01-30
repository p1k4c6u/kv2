# kv.ee Scraper

A web scraper for kv.ee (Estonian real estate marketplace) that extracts property listings and tracks price changes over time.

## Features

- Scrapes apartment listings from kv.ee
- Extracts structured data (price, area, rooms, etc.)
- Stores listings in PostgreSQL database
- Tracks price/content changes with snapshots
- Handles security challenges (manual CAPTCHA solving)

## Requirements

- Python 3.10+
- PostgreSQL database
- Chromium browser (installed automatically by Playwright)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd kv2
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your database connection string
   ```

4. Set the DATABASE_URL environment variable:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/kv_scraper"
   ```

## Usage

Run the scraper:

```bash
python -m kv
```

You will be prompted to enter an area (city or county):
- Cities: `tallinn`, `tartu`
- Counties: `harjumaa`, `jogevamaa`

The scraper will:
1. Initialize the database tables (if not exists)
2. Search for listings in the specified area
3. Crawl each listing and extract data
4. Save to database with change tracking

## Database Schema

### kv_listings
Main table storing the latest state of each listing:
- `listing_id` - Unique identifier from kv.ee
- `url` - Listing URL
- `title`, `price_eur`, `rooms`, `total_area`, etc.
- `last_seen_at` - Last scrape timestamp

### kv_listing_snapshots
Historical snapshots for tracking changes:
- `snapshot_id` - Auto-incrementing ID
- `listing_id` - Reference to main listing
- `content_hash` - Hash of content for deduplication
- `fetched_at` - Snapshot timestamp

## Project Structure

```
kv2/
├── kv/
│   ├── __init__.py    # Package initialization
│   ├── main.py        # Entry point
│   ├── search.py      # Search page crawler
│   ├── listings.py    # Individual listing parser
│   ├── browser.py     # Playwright browser wrapper
│   └── db.py          # PostgreSQL database interface
├── requirements.txt   # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

## Notes

- The browser runs in visible mode (not headless) to handle CAPTCHAs
- A browser profile is saved in `kv_profile/` to preserve cookies
- Rate limiting: 1 second delay between page requests
