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
"""

UPSERT_LATEST = """
INSERT INTO kv_listings (
  listing_id, url, title, price_eur, eur_per_m2, rooms, bedrooms, total_area, floors,
  year_built, condition, ownership, plot_area, cadastral_nr, energy_class,
  additional_info, additional_info_raw, description, raw, last_seen_at
)
VALUES (
  %(listing_id)s, %(url)s, %(title)s, %(price_eur)s, %(eur_per_m2)s, %(rooms)s, %(bedrooms)s, %(total_area)s, %(floors)s,
  %(year_built)s, %(condition)s, %(ownership)s, %(plot_area)s, %(cadastral_nr)s, %(energy_class)s,
  %(additional_info)s, %(additional_info_raw)s, %(description)s, %(raw)s, now()
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

def init_db():
    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SQL)
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
        "content_hash": content_hash,
    }

    with psycopg.connect(DB_URL, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(UPSERT_LATEST, params)
            cur.execute(INSERT_SNAPSHOT_IF_NEW, params)
        conn.commit()
