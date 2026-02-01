# db.py

import os
import json
import hashlib
import psycopg

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Please set it to your PostgreSQL connection string, e.g.: "
        "postgresql://user:password@localhost:5432/dbname"
    )

# Railway uses postgres:// but psycopg3 requires postgresql://
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS kv_listings (
  listing_id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  title TEXT,
  price_eur INTEGER,
  eur_per_m2 INTEGER,
  rooms TEXT,
  bedrooms TEXT,
  total_area TEXT,
  floors TEXT,
  year_built TEXT,
  condition TEXT,
  ownership TEXT,
  plot_area TEXT,
  cadastral_nr TEXT,
  energy_class TEXT,
  additional_info TEXT[],
  additional_info_raw TEXT,
  description TEXT,
  raw JSONB,
  is_owner_direct BOOLEAN,
  seller_info TEXT,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS kv_listing_snapshots (
  snapshot_id BIGSERIAL PRIMARY KEY,
  listing_id TEXT NOT NULL REFERENCES kv_listings(listing_id) ON DELETE CASCADE,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_hash TEXT NOT NULL,
  price_eur INTEGER,
  eur_per_m2 INTEGER,
  additional_info TEXT[],
  description TEXT,
  raw JSONB
);

CREATE INDEX IF NOT EXISTS idx_snapshots_listing_time
  ON kv_listing_snapshots(listing_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS kv_analysis (
  listing_id TEXT PRIMARY KEY REFERENCES kv_listings(listing_id) ON DELETE CASCADE,
  score INTEGER NOT NULL,
  breakdown JSONB,
  summary TEXT,
  model TEXT,
  analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_score
  ON kv_analysis(score DESC);
"""

UPSERT_LATEST = """
INSERT INTO kv_listings (
  listing_id, url, title, price_eur, eur_per_m2, rooms, bedrooms, total_area, floors,
  year_built, condition, ownership, plot_area, cadastral_nr, energy_class,
  additional_info, additional_info_raw, description, raw, is_owner_direct, seller_info, last_seen_at
)
VALUES (
  %(listing_id)s, %(url)s, %(title)s, %(price_eur)s, %(eur_per_m2)s, %(rooms)s, %(bedrooms)s, %(total_area)s, %(floors)s,
  %(year_built)s, %(condition)s, %(ownership)s, %(plot_area)s, %(cadastral_nr)s, %(energy_class)s,
  %(additional_info)s, %(additional_info_raw)s, %(description)s, %(raw)s, %(is_owner_direct)s, %(seller_info)s, now()
)
ON CONFLICT (listing_id) DO UPDATE SET
  url = EXCLUDED.url,
  title = EXCLUDED.title,
  price_eur = EXCLUDED.price_eur,
  eur_per_m2 = EXCLUDED.eur_per_m2,
  rooms = EXCLUDED.rooms,
  bedrooms = EXCLUDED.bedrooms,
  total_area = EXCLUDED.total_area,
  floors = EXCLUDED.floors,
  year_built = EXCLUDED.year_built,
  condition = EXCLUDED.condition,
  ownership = EXCLUDED.ownership,
  plot_area = EXCLUDED.plot_area,
  cadastral_nr = EXCLUDED.cadastral_nr,
  energy_class = EXCLUDED.energy_class,
  additional_info = EXCLUDED.additional_info,
  additional_info_raw = EXCLUDED.additional_info_raw,
  description = EXCLUDED.description,
  raw = EXCLUDED.raw,
  is_owner_direct = EXCLUDED.is_owner_direct,
  seller_info = EXCLUDED.seller_info,
  last_seen_at = now();
"""

INSERT_SNAPSHOT_IF_NEW = """
INSERT INTO kv_listing_snapshots (
  listing_id, content_hash, price_eur, eur_per_m2, additional_info, description, raw
)
SELECT
  %(listing_id)s, %(content_hash)s, %(price_eur)s, %(eur_per_m2)s, %(additional_info)s, %(description)s, %(raw)s
WHERE NOT EXISTS (
  SELECT 1 FROM kv_listing_snapshots
  WHERE listing_id = %(listing_id)s
    AND content_hash = %(content_hash)s
);
"""


def _compute_hash(d: dict) -> str:
    # hash only the fields you care about for "change"
    payload = {
        "title": d.get("title"),
        "price_eur": d.get("price_eur"),
        "eur_per_m2": d.get("eur_per_m2"),
        "additional_info": d.get("additional_info"),
        "description": d.get("description"),
    }
    b = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


MIGRATE_SQL = """
ALTER TABLE kv_listings ADD COLUMN IF NOT EXISTS is_owner_direct BOOLEAN;
ALTER TABLE kv_listings ADD COLUMN IF NOT EXISTS seller_info TEXT;
"""


def init_db():
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
            cur.execute(MIGRATE_SQL)
        conn.commit()


def save_listing(data: dict):
    """
    Saves:
      1) latest row in kv_listings (upsert)
      2) snapshot row in kv_listing_snapshots only if changed
    """
    if "listing_id" not in data:
        raise ValueError("data must include listing_id")

    content_hash = _compute_hash(data)

    params = {
        "listing_id": data["listing_id"],
        "url": data.get("url"),
        "title": data.get("title"),
        "price_eur": data.get("price_eur"),
        "eur_per_m2": data.get("eur_per_m2"),
        "rooms": data.get("rooms"),
        "bedrooms": data.get("bedrooms"),
        "total_area": data.get("total_area"),
        "floors": data.get("floors"),
        "year_built": data.get("year_built"),
        "condition": data.get("condition"),
        "ownership": data.get("ownership"),
        "plot_area": data.get("plot_area"),
        "cadastral_nr": data.get("cadastral_nr"),
        "energy_class": data.get("energy_class"),
        "additional_info": data.get("additional_info"),
        "additional_info_raw": data.get("additional_info_raw"),
        "description": data.get("description"),
        "raw": json.dumps(data, ensure_ascii=False),
        "is_owner_direct": data.get("is_owner_direct"),
        "seller_info": data.get("seller_info"),
        "content_hash": content_hash,
    }

    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(UPSERT_LATEST, params)
            cur.execute(INSERT_SNAPSHOT_IF_NEW, params)
        conn.commit()


# Analysis functions

UPSERT_ANALYSIS = """
INSERT INTO kv_analysis (listing_id, score, breakdown, summary, model, analyzed_at)
VALUES (%(listing_id)s, %(score)s, %(breakdown)s, %(summary)s, %(model)s, now())
ON CONFLICT (listing_id) DO UPDATE SET
  score = EXCLUDED.score,
  breakdown = EXCLUDED.breakdown,
  summary = EXCLUDED.summary,
  model = EXCLUDED.model,
  analyzed_at = now();
"""


def save_analysis(
    listing_id: str, score: int, breakdown: dict, summary: str, model: str
):
    """Save LLM analysis results for a listing."""
    params = {
        "listing_id": listing_id,
        "score": score,
        "breakdown": json.dumps(breakdown) if breakdown else None,
        "summary": summary,
        "model": model,
    }
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(UPSERT_ANALYSIS, params)
        conn.commit()


def get_analyzed_listing_ids() -> set[str]:
    """Get set of listing IDs that have been analyzed."""
    query = "SELECT listing_id FROM kv_analysis"
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return {row[0] for row in cur.fetchall()}


def get_listings_with_analysis(
    limit: int = 100,
    offset: int = 0,
    min_score: int | None = None,
    max_price: int | None = None,
    min_rooms: int | None = None,
    only_analyzed: bool = False,
    sort_by: str = "score",
    sort_order: str = "desc",
) -> list[dict]:
    """
    Get listings with their analysis data.
    Returns listings joined with analysis (if exists).
    """
    # Build WHERE conditions
    conditions = []
    params = {}

    # Hard filter: only owner-direct listings are visible in the app
    conditions.append("l.is_owner_direct = true")

    if min_score is not None:
        conditions.append("a.score >= %(min_score)s")
        params["min_score"] = min_score

    if max_price is not None:
        conditions.append("l.price_eur <= %(max_price)s")
        params["max_price"] = max_price

    if min_rooms is not None:
        conditions.append(
            "CAST(NULLIF(regexp_replace(l.rooms, '[^0-9]', '', 'g'), '') AS INTEGER) >= %(min_rooms)s"
        )
        params["min_rooms"] = min_rooms

    if only_analyzed:
        conditions.append("a.listing_id IS NOT NULL")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # Build ORDER BY
    valid_sort_columns = {
        "score": "COALESCE(a.score, 0)",
        "price": "COALESCE(l.price_eur, 0)",
        "date": "l.last_seen_at",
        "eur_per_m2": "COALESCE(l.eur_per_m2, 0)",
    }
    sort_col = valid_sort_columns.get(sort_by, "COALESCE(a.score, 0)")
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    query = f"""
    SELECT 
        l.listing_id, l.url, l.title, l.price_eur, l.eur_per_m2,
        l.rooms, l.bedrooms, l.total_area, l.floors, l.year_built,
        l.condition, l.energy_class, l.description, l.last_seen_at,
        a.score, a.breakdown, a.summary, a.model, a.analyzed_at
    FROM kv_listings l
    LEFT JOIN kv_analysis a ON l.listing_id = a.listing_id
    {where_clause}
    ORDER BY {sort_col} {sort_dir}
    LIMIT %(limit)s OFFSET %(offset)s
    """
    params["limit"] = limit
    params["offset"] = offset

    results = []
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            for row in cur.fetchall():
                d = dict(zip(columns, row))
                # Parse JSONB breakdown
                if d.get("breakdown") and isinstance(d["breakdown"], str):
                    d["breakdown"] = json.loads(d["breakdown"])
                results.append(d)

    return results


def get_listing_by_id(listing_id: str) -> dict | None:
    """Get a single listing with its analysis."""
    query = """
    SELECT 
        l.*,
        a.score, a.breakdown, a.summary, a.model, a.analyzed_at
    FROM kv_listings l
    LEFT JOIN kv_analysis a ON l.listing_id = a.listing_id
    WHERE l.listing_id = %(listing_id)s
      AND l.is_owner_direct = true
    """
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"listing_id": listing_id})
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc[0] for desc in cur.description]
            d = dict(zip(columns, row))
            if d.get("breakdown") and isinstance(d["breakdown"], str):
                d["breakdown"] = json.loads(d["breakdown"])
            if d.get("raw") and isinstance(d["raw"], str):
                d["raw"] = json.loads(d["raw"])
            return d


def get_stats() -> dict:
    """Get dashboard statistics."""
    query = """
    SELECT 
        COUNT(*) as total_listings,
        COUNT(a.listing_id) as analyzed_count,
        AVG(a.score) as avg_score,
        MIN(a.score) as min_score,
        MAX(a.score) as max_score,
        AVG(l.price_eur) as avg_price,
        MIN(l.price_eur) as min_price,
        MAX(l.price_eur) as max_price
    FROM kv_listings l
    LEFT JOIN kv_analysis a ON l.listing_id = a.listing_id
    WHERE l.is_owner_direct = true
    """
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            row = cur.fetchone()
            columns = [desc[0] for desc in cur.description]
            return dict(zip(columns, row))
